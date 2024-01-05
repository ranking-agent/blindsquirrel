from neo4j import GraphDatabase

class Neo4j:

    def __init__(self,db,pw):
        self.driver = self.get_driver(db,pw)
        self.name_to_curie = {}

    def get_driver(self, db, pw):
        return GraphDatabase.driver(f'bolt://{db}:7687', auth=('neo4j', pw))

    def get_name(self, curie):
        """Given a curie, return the name of the node in the neo4j.
        1. Query the neo4j to return the name of the node.
        2. Put the curie and name of the node into name_to_curie
        3. Return the name
        """
        with self.driver.session() as session:
            results = session.run(f'MATCH (a) WHERE a.id = "{curie}" RETURN a.name as n')
            for result in results:
                self.name_to_curie[result['n']] = curie
                return result['n']

    def get_neighborhood_schema(self, name):
        """Given a name, find the types of connections for that node in the neo4j.
        1. Get the curie for the name from name_to_curie.
        2. Query the neo4j to return counts for (curie, predicate, ?)
        3. Query then neo4j to return counts for (?, predicate, curie)
        4. Return a list of tuples [ (name, predicate, count), ..., (count, predicate, name), ...]
        """
        results = []
        curie = self.name_to_curie[name]
        with self.driver.session() as session:
            forward_results = session.run(f'MATCH (a)-[r]->(b) WHERE a.id = "{curie}" RETURN type(r) as r, COUNT(b) as c')
            for result in forward_results:
                results.append( (name, result['r'], result['c']) )
            reverse_results = session.run(f'MATCH (a)<-[r]-(b) WHERE a.id = "{curie}" RETURN type(r) as r, COUNT(b) as c')
            for result in reverse_results:
                results.append( (result['c'], result['r'], name) )
        return results

    def get_edges(self, edge):
        """Given an edge, which is either of the form (name, predicate, count) or (count, predicate, name),
        return a list of edges that match the pattern.
        1. Get the curie for the name from name_to_curie.
        2. Query the neo4j to return the curies and names of the nodes that match the pattern.
        3. Put the curie and name of each result into name_to_curie
        4. Return a list of tuples [ (name, predicate, newname)] or [ (newname, predicate, name)]
        """
        results = []
        if isinstance(edge[2], int):
            # This is a forward edge
            curie = self.name_to_curie[edge[0]]
            with self.driver.session() as session:
                cypher = f'MATCH (a)-[r:`{edge[1]}`]->(b) WHERE a.id = "{curie}" RETURN b.id as b, b.name as n'
                forward_results = session.run(cypher)
                for result in forward_results:
                    self.name_to_curie[result['n']] = result['b']
                    results.append( (edge[0], edge[1], result["n"]) )
        else:
            # This is a reverse edge
            curie = self.name_to_curie[edge[2]]
            with self.driver.session() as session:
                reverse_results = session.run(f'MATCH (a)<-[r:`{edge[1]}`]-(b) WHERE a.id = "{curie}" RETURN b.id as b, b.name as n')
                for result in reverse_results:
                    self.name_to_curie[result['n']] = result['b']
                    results.append( (result["n"], edge[1], edge[2]) )
        return results

    def detail_edge(self, edge):
        subject = self.name_to_curie[edge[0]]
        predicate = edge[1]
        object = self.name_to_curie[edge[2]]
        returns = []
        with self.driver.session() as session:
            cypher = f'MATCH (a)-[r:`{predicate}`]->(b) WHERE a.id = "{subject}" and b.id = "{object}" RETURN r'
            print(cypher)
            edges = session.run(f'MATCH (a)-[r:`{edge[1]}`]->(b) WHERE a.id = "{subject}" and b.id = "{object}" RETURN r')
            for edge in edges:
                returns.append(edge['r']._properties)
        return returns
