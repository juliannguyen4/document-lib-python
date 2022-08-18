import aerospike
from aerospike import Client

from aerospike_helpers import cdt_ctx
from aerospike_helpers.operations import map_operations
from aerospike_helpers.operations import list_operations
from aerospike_helpers.operations import operations

from jsonpath_ng import jsonpath, parse

import re

from typing import Any

class DocumentClient:
    """Client to run JSON queries"""

    def __init__(self, client: Client):
        self.client = client

    # Split up a valid JSON path into map and list access tokens
    def tokenize(self, jsonPath):
        # First divide JSON path into "big" tokens
        # using map separator "."
        # Example:
        # "$[1].b.c[2]" -> ["$[1]", "b", "c[2]]"
        bigTokens = jsonPath.split(".")

        # Then divide each big token into "small" tokens
        # using list separator "[<index>]"
        # Example:
        # [$[1], b, c[2]] -> ["$", 1, "b", "c", 2]
        results = []
        for bigToken in bigTokens:
            smallTokens = re.split("\[|\]", bigToken)
            # Remove empty small tokens
            while "" in smallTokens:
                smallTokens.remove("")
    
            # First small token is always a map access or $
            # Every small token after it is a list access
            foundMapAccessOrRoot = False
            for smallToken in smallTokens:
                if foundMapAccessOrRoot:
                    # Encode list access token as an integer
                    smallToken = int(smallToken)
                else:
                    # Encode map access token as a string
                    foundMapAccessOrRoot = True

                results.append(smallToken)
        return results

    def buildContextArray(self, tokens):
        ctxs = []
        for token in tokens:
            if type(token) == int:
                # List access
                ctx = cdt_ctx.cdt_ctx_list_index(token)
            elif token == '$':
                # Don't need context for root
                continue
            else:
                # Map access
                ctx = cdt_ctx.cdt_ctx_map_key(token)
            ctxs.append(ctx)
        return ctxs

    def get(self, key: tuple, binName: str, jsonPath: str, readPolicy: dict = None) -> Any:
        """
        Get object(s) from a JSON document using JSON path.

        If multiple objects are matched, they will be returned as a :class:`list`.
        Otherwise, the object itself is returned.

        :param tuple key: the key of the record
        :param str binName: the name of the bin containing the JSON document
        :param str jsonPath: JSON path to retrieve the object
        :param dict readPolicy: the read policy for get() operation

        :return: :py:obj:`Any`
        :raises: :exc:`KeyNotFound`
        """

        # Validate JSON path

        # JSON path must start at document root
        if jsonPath and jsonPath.startswith("$") == False:
            raise ValueError("Invalid JSON path")

        # Check for syntax errors
        try:
            parse(jsonPath)
        except Exception:
            raise ValueError("Invalid JSON path")

        # Divide JSON path into two parts
        # The first part does not have advanced operations
        # The second part starts with the first advanced operation in the path

        # Get substring in path beginning with the first advanced operation
        advancedOps = ["[*]", "..", "[?"]
        # Look for operations in path
        startIndices = [jsonPath.find(op) for op in advancedOps]
        # Filter out ones that aren't found
        startIndices = list(filter(lambda index: index >= 1, startIndices))
        if startIndices:
            startIndex = min(startIndices)
        else:
            # No advanced operations found
            startIndex = -1

        advancedJsonPath = None
        if startIndex > 0:
            # Treat fetched JSON document as root document
            advancedJsonPath = "$" + jsonPath[startIndex:]
            jsonPath = jsonPath[:startIndex]

        # Split up JSON path into tokens
        tokens = self.tokenize(jsonPath)

        # Then use tokens to build context arrays
        # except the last token
        lastToken = tokens.pop()
        ctxs = self.buildContextArray(tokens)

        # Create get operation using last token
        if type(lastToken) == int:
            op = list_operations.list_get_by_index(binName, lastToken, aerospike.LIST_RETURN_VALUE, ctxs)
        elif lastToken == "$":
            # Get whole document
            op = operations.read(binName)
        else:
            op = map_operations.map_get_by_key(binName, lastToken, aerospike.MAP_RETURN_VALUE, ctxs)

        _, _, bins = self.client.operate(key, [op])
        results = bins[binName]

        # Use JSONPath library to perform advanced ops on fetched document
        if advancedJsonPath:
            jsonPathExpr = parse(advancedJsonPath)
            results = [match.value for match in jsonPathExpr.find(results)]

        return results

    def put(self, key: tuple, binName: str, jsonPath: str, obj: Any, writePolicy: dict = None):
        """
        Put an object into a JSON document using JSON path

        :param tuple key: the key of the record
        :param str binName: the name of the bin containing the JSON document
        :param str jsonPath: JSON path location to store the object
        :param dict writePolicy: the write policy for put() operation
        
        """
        pass

    def append(self, key: tuple, binName: str, jsonPath: str, obj, writePolicy: dict = None):
        """
        Append an object to a list in a JSON document using JSON path

        :param tuple key: the key of the record
        :param str binName: the name of the bin containing the JSON document
        :param str jsonPath: JSON path ending with a list
        :param dict writePolicy: the write policy for operate() operation
        
        """
        pass

    def delete(self, key: tuple, binName: str, jsonPath: str):
        """
        Delete an object in a JSON document using JSON path

        :param tuple key: the key of the record
        :param str binName: the name of the bin containing the JSON document
        :param str jsonPath: JSON path of object to delete
        :param dict writePolicy: the write policy for operate() operation

        """
        pass
