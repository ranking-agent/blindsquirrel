import uuid,os
import requests
import json
import time

class BlackboardConversation():
    """A conversation with an OpenAI chat completion model.  Instead of always passing the entire previous
    conversation as the prompt, we maintain a blackboard of information that we have learned and use that to
    create the prompt.  One component of the blackboard is a knowledge graph that has been extracted from ROBOKOP KG.
    The requests and responses are serialized so that they are easily viewed/parsed, and also so that we can pick back
    up after running for several iterations."""
    def __init__(self, controller):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.create_serialization("conversations")
        self.controller = controller

    def create_serialization(self, conversation_directory):
        # Create a unique identifier for this conversation
        self.conversation_identifier = str(uuid.uuid4())
        # Create a directory for this conversation
        self.conversation_directory = os.path.join(conversation_directory, self.conversation_identifier)
        os.mkdir(self.conversation_directory)

    def iterate(self, steps=1):
        for step in range(steps):
            print(f"Step {step}")
            payload = self.controller.generate_payload()
            response = self.execute(payload)
            content = json.loads( response["choices"][0]["message"]["content"] )
            self.controller.update(content)
            self.serialize(payload, response, step)
            #sleep for 60 seconds to avoid rate limiting
            print ('  ...zzz')
            time.sleep(60)
            print( "  ...awake")

    def execute(self, payload):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        # Todo: build in some resiliency here
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        if response.status_code != 200:
            print(response.text)
            raise Exception("OpenAI API call failed")
        jsonresponse = response.json()
        finish_reason = jsonresponse["choices"][0]["finish_reason"]
        if not finish_reason == "stop":
            raise Exception(f"OpenAI API call failed. finish_reason = {finish_reason}")
        return jsonresponse

    def serialize(self, payload, response, step):
        with open(os.path.join(self.conversation_directory, f"step_{step}.json"), "w") as out:
            json.dump({"payload": payload, "response": response, "blackboard": self.controller.generate_blackboard()}, out, indent=4)