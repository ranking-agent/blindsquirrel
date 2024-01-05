import sys
import yaml, requests
from operations import Neo4j
import json
from conversation import BlackboardConversation

class SquirrelController:
    def __init__(self, db, pw, curie1, curie2):
        self.neo4j = Neo4j(db, pw)
        self.infores_catalog = None
        self.curie1 = curie1
        self.curie2 = curie2
        self.name1 = self.neo4j.get_name(curie1)
        self.name2 = self.neo4j.get_name(curie2)
        self.kg = self.get_neighborhood_schema(self.name1)
        self.kg += self.get_neighborhood_schema(self.name2)
        self.summary = ""
        self.observations = []
        self.actions = [{"action": "expand_node", "argument": self.name1}, {"action": "expand_node", "argument": self.name2}]

    def generate_payload(self):
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "system",
                    "content": self.generate_system_prompt()
                },
                {
                    "role": "user",
                    "content": json.dumps(self.generate_blackboard())
                }
            ]
        }
        return payload

    def generate_blackboard(self):
        blackboard = {
            "knowledge graph": self.kg,
            "observations": self.observations,
            "summary": self.summary,
            "previous_actions": self.actions
        }
        return blackboard

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
        source_details = {}
        try:
            source_details["source_name"] = self.infores_catalog[source]["name"]
        except KeyError:
            pass
        try:
            source_details["source_description"] = self.infores_catalog[source]["description"]
        except:
            pass
        return source_details

    def pull_infores_catalog(self):
        url = "https://raw.githubusercontent.com/biolink/biolink-model/master/infores_catalog.yaml"
        direct_yaml =  yaml.load(requests.get(url).text, Loader=yaml.FullLoader)
        self.infores_catalog = {infores["id"]:infores for infores in direct_yaml["information_resources"]}

    def update(self, response):
        # Update the blackboard
        self.actions.append( {"action": response["action"], "argument": response["argument"]} )
        if isinstance(response["new_observations"],list):
            self.observations += response["new_observations"]
        else:
            self.observations.append(response["new_observations"])
        self.summary = response["summary"]
        argument = response["argument"]
        if response["action"] == "complete_edge":
            self.kg += self.get_edges(argument)
            # This is coming in as a list, so we need to turn it into a tuple
            try:
                self.kg.remove(tuple(response["argument"]))
            except ValueError:
                print("Edge not found in KG" )
                print(json.dumps(response["argument"]))
                print('')
                for edge in self.kg:
                    print(edge)
        elif response["action"] == "detail_edge":
            self.observations.append(f"Edge detail for {response['argument']}: {json.dumps(self.detail_edge(argument))}")
        elif response["action"] == "expand_node":
            self.kg += self.get_neighborhood_schema(argument)
            # Remove dupes
            self.kg = list(set(self.kg))
        else:
            raise Exception("Invalid action:"+response["action"]+" for argument:"+response["argument"])

    def generate_system_prompt(self):
        prompt = \
f""" You are a translational researcher exploring the relationship between {self.name1} and {self.name2}.   
The tool at your disposal is a large knowledge graph (KG).  This KG is composed of many (subject, relationship, object) triples.    
Your goal is to explore the graph around the nodes for {self.name1} and {self.name2} until you understand and can explain 
the relationship between these entities, not simply in terms of the relationship type, but also in terms of the
mechanism for the relationship.

At each step I will give you a blackboard representation of the previously generated understanding. 
The blackboard will be in the following format:
{{
    "knowledge graph": [],
    "observations": [], 
    "summary": "",
    "previous_actions": []
}}
The knowledge graph is a list of (node,edge,node) triples.  
For new nodes, found by queries, the triples will be partial.  For instance
(isopropyl alcohol, causes, 28) will tell you that there are 28 "causes" edges with isopropyl alcohol as the 
subject, but you do not yet know the objects.

The observations are a list of statements that you have made about the relationship between {self.name1} and {self.name2}.
These will provide the breadcrumbs for your exploration. The observations may be hypotheses, relevant facts, partial 
 syntheses of information, or notes for future exploration. These observations should be granular.

The summary is a text description of your current understanding of the relationship between {self.name1} and {self.name2}. 
It should be a summary of the observations, and the knowledge graph, but it may also contain other information that you have learned.

Both the observations and the summary must be as concise as possible.

The previous_actions are a list of the previous actions that you have taken.  Repeating actions will not lead to new 
information and should be avoided.

You will then respond only in the following JSON format:
{{
    "new_observations": [],
    "summary": "",
    "action": "",
    "argument": ""
}}
1. New observations is a list of strings that will be added to the observation on the blackboard for future use by yourself or other reasoning tools.
2. The summary will also be posted to the blackboard
3. The action value is one of "complete_edge", "detail_edge", "expand_node".
   3a. If the action is "complete_edge", the argument value is a partial triple (node,predicate,count) or (count,predicate,node) that you would like to complete.
       In this case, all of the edges that match the partial triple will be added to the KG, which usually add new nodes.
   3b. If the action is "detail_edge", the argument should be a complete (node,predicate,node) triple. In this case, I will return details about the edge, 
       often in the form of PUBMED abstracts that support the edge.  I may also return information about the database that supplied the edge, or
       parameters or qualifications associated with the edge.
   3c. If the action is "expand_node", the argument should be a node name.  In this case, I will return the partial edges associated with the node.
   
   NEVER repeat an action/argument pair that has already been used and is in the "previous_actions" of the blackboard.
   
"""
        return prompt


if __name__ == "__main__":
    # get the db and pw from the command line
    db = sys.argv[1]
    pw = sys.argv[2]
    curie1 = "MONDO:0010778"  # Cyclic Vomiting Syndrome
    curie2 = "PUBCHEM.COMPOUND:3776"  # isopropyl alcohol
    squirrel = SquirrelController(db, pw, curie1, curie2)
    conversation = BlackboardConversation(squirrel)
    conversation = conversation.iterate(20)