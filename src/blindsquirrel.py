import sys
import yaml, requests
from operations import Neo4j

class Squirrel:
    def __init__(self, db, pw, curie1, curie2):
        self.neo4j = Neo4j(db, pw)
        self.infores_catalog = None
        self.curie1 = curie1
        self.curie2 = curie2
        self.name1 = self.neo4j.get_name(curie1)
        self.name2 = self.neo4j.get_name(curie2)
        self.kg = []
        self.understanding = ""

    def get_neighborhood_schema(self, name):
        return self.neo4j.get_neighborhood_schema(name)

    def get_edges(self, edge):
        return self.neo4j.get_edges(edge)

    def detail_edge(self, edge):
        # These are ignorable because they are either reproducing things we already know or are being handled specifically
        ignorable_properties = ["biolink:primary_knowledge_source", "predicate", "knowledge_source", "subject", "biolink:aggregator_knowledge_source",
                                "id", "object"]
        edge_properties = self.neo4j.detail_edge(edge)
        print(edge_properties[0])
        usable_properties = self.generate_source_text(edge_properties[0]["biolink:primary_knowledge_source"])
        for property in edge_properties[0]:
            if property in ignorable_properties:
                continue
            else:
                if property == "FAERS_llr":
                    usable_properties["Log Likelihood Ratio"] = edge_properties[0][property]
                elif property in ["object_direction_qualifier", "object_aspect_qualifier", "qualified_predicate", "subject_direction_qualifier", "subject_aspect_qualifier"]:
                    usable_properties[property] = edge_properties[0][property]
                else:
                    print(property, edge_properties[0][property])
        return usable_properties

    def generate_source_text(self, source):
        if self.infores_catalog is None:
            self.pull_infores_catalog()
        return { "source name": self.infores_catalog[source]["name"], "source description": self.infores_catalog[source]["description"]}

    def pull_infores_catalog(self):
        url = "https://raw.githubusercontent.com/biolink/biolink-model/master/infores_catalog.yaml"
        direct_yaml =  yaml.load(requests.get(url).text, Loader=yaml.FullLoader)
        self.infores_catalog = {infores["id"]:infores for infores in direct_yaml["information_resources"]}

    def generate_initial_chat_prompt(self):
        self.kg = self.get_neighborhood_schema(self.name1)
        self.kg += self.get_neighborhood_schema(self.name2)
        prompt = \
f""" You are a translational researcher exploring the relationship between {self.name1} and {self.name2}.   
The tool at your disposal is a large knowledge graph (KG).  This KG is composed of many (subject, relationship, object) triples.    
Your goal is to explore the graph around the nodes for {self.name1} and {self.name2} until you understand and can explain 
the relationship between these entities, not simply in terms of the relationship type, but also in terms of the
mechanism for the relationship.

At each step I will give you a representation of the current graph as a list of (node,edge,node) triples.  
For new nodes, found by queries, the triples will be partial.  For instance
(isopropyl alcohol, causes, 28) will tell you that there are 28 "causes" edges with isopropyl alcohol as the 
subject, but you do not yet know the objects.

You will then respond only in the following JSON format:
{{
    "understanding": "",
    "action": "",
    "argument": ""
}}
1. The understanding value contains text describing your current understanding of the relationship between {self.name1} and {self.name2}.
2. The action value is one of "complete_edge", "detail_edge", "expand_node".
   2a. If the action is "complete_edge", the argument value is a partial triple (node,predicate,count) or (count,predicate,node) that you would like to complete.
       In this case, all of the edges that match the partial triple will be added to the KG, which usually add new nodes.
   2b. If the action is "detail_edge", the argument should be a complete (node,predicate,node) triple. In this case, I will return details about the edge, 
       often in the form of PUBMED abstracts that support the edge.  I may also return information about the database that supplied the edge, or
       parameters or qualifications associated with the edge.
   2c. If the action is "expand_node", the argument should be a node name.  In this case, I will return the partial edges associated with the node.

I have begun by running "expand_node" on {self.name1} and {self.name2}.
Knowledge Graph:
"""
        for triple in self.kg:
            prompt += str(triple) + "\n"

        return prompt

if __name__ == "__main__":
    # get the db and pw from the command line
    db = sys.argv[1]
    pw = sys.argv[2]
    # create the blind squirrel
    curie1 = "MONDO:0010778"  # Cyclic Vomiting Syndrome
    curie2 = "PUBCHEM.COMPOUND:3776"  # isopropyl alcohol
    squirrel = Squirrel(db, pw, curie1, curie2)

    # generate the initial chat prompt
    #prompt = squirrel.generate_initial_chat_prompt()
    #print(prompt)

    # Complete edge on CVS has phenotype:
    #new_edges = squirrel.get_edges( ('cyclic vomiting syndrome', 'biolink:has_phenotype', 24) )
    #for edge in new_edges:
    #   print(edge)

    #Complete edge on Isopropyl Alcohol causes_adverse_event
    #new_edges = squirrel.get_edges( ('Isopropyl Alcohol', 'biolink:has_adverse_event', 164) )
    #for edge in new_edges:
    #    print(edge)

    #detail edge:
    #squirrel.neo4j.name_to_curie['Abdominal Pain'] = "HP:0002027"
    #details = squirrel.detail_edge( ('Isopropyl Alcohol', 'biolink:has_adverse_event', 'Abdominal Pain') )
    #for k,v in details.items():
    #   print(f"{k}: {v}")

    # Complete edge on CVS causes:
    #new_edges = squirrel.get_edges(('cyclic vomiting syndrome', 'biolink:causes', 1))
    #for edge in new_edges:
    #   print(edge)

    # detail edge:
    #squirrel.neo4j.name_to_curie['TRNL1'] = "NCBIGene:4567"
    #details = squirrel.detail_edge( ('cyclic vomiting syndrome', 'biolink:causes', 'TRNL1') )
    #for k,v in details.items():
    #    print(f"{k}: {v}")

    # Complete Edge
    #new_edges = squirrel.get_edges( ('Isopropyl Alcohol', 'biolink:treats', 20) )
    #for edge in new_edges:
    #   print(edge)

    # detail edge:
    #squirrel.neo4j.name_to_curie['Nausea and vomiting'] = "HP:0002017"
    #details = squirrel.detail_edge( ('Isopropyl Alcohol', 'biolink:treats', 'Nausea and vomiting') )
    #for k,v in details.items():
    #    print(f"{k}: {v}")

    # Complete Edge
    #new_edges = squirrel.get_edges( ('Isopropyl Alcohol', 'biolink:affects', 70) )
    #for edge in new_edges:
    #   print(edge)

    # detail edge:
    new_edges = squirrel.get_edges( ('Isopropyl Alcohol', 'biolink:affects', 70) ) # gets adh1a mapping
    details = squirrel.detail_edge(('Isopropyl Alcohol', 'biolink:affects', 'ADH1A') )
    for k,v in details.items():
        print(f"{k}: {v}")

