n this notebooks you will learn how to trace your MistralAI Api calls using W&B Weave, how to evaluate the performance of your models and how to close the gap by leveraging the MistralAI finetuning capabilities.

In this notebooks we will fine-tune a mistral 7b model as an LLM Judge. This idea comes from the amazing blog post from Eugene. The main goal is to fine-tune a small model like Mistral 7B to act as an hallucination judge. We will do this in 2 steps:

Training on a Factual Inconsistency Benchmark challenging dataset to improve the model performance to detect hallucination by detecting inconsistencies beween a piece of text and a "summary"
We will then mix that dataset with Wikipedia summaries dataset to increase the performance even more.


Weights & Biases: https://wandb.ai/
Mistral finetuning docs: https://docs.mistral.ai/capabilities/finetuning/
Tracing with W&B Weave: https://wandb.me/weave
Load some data

# !pip install "mistralai==0.4.2" "weave==0.50.7"
let's import the relevant pieces


import os, asyncio, json
from pathlib import Path

import weave

from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

client = MistralClient(api_key=os.environ["MISTRAL_API_KEY"])
some globals


DATA_PATH = Path("./data")
NUM_SAMPLES = 100 # Number of samples to use for evaluation, use None for all
PROJECT_NAME = "llm-judge-webinar"

weave.init(PROJECT_NAME)

def read_jsonl(path):
    "returns a list of dictionaries"
    with open(path, 'r') as file:
        return [json.loads(line) for line in file]

train_ds = read_jsonl(DATA_PATH / "fib-train.jsonl")
val_ds = read_jsonl(DATA_PATH / "fib-val.jsonl")[0:NUM_SAMPLES]


We are going to map to 0 and 1 for the sake of it!


len(train_ds)

train_ds[0]
You will probably integrate MistralAI API calls in your codebase by creating a function like the one below:


@weave.op()  # <---- add this and you are good to go
def call_mistral(model:str, messages:list, **kwargs) -> str:
    "Call the Mistral API"
    chat_response = client.chat(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        **kwargs,
    )
    return json.loads(chat_response.choices[0].message.content)
Let's create a prompt that explains the task...


prompt = """You are an expert to detect factual inconsistencies and hallucinations. You will be given a document and a summary.
- Carefully read the full document and the provided summary.
- Identify Factual Inconsistencies: any statements in the summary that are not supported by or contradict the information in the document.
Factually Inconsistent: If any statement in the summary is not supported by or contradicts the document, label it as 0
Factually Consistent: If all statements in the summary are supported by the document, label it as 1

Highlight or list the specific statements in the summary that are inconsistent.
Provide a brief explanation of why each highlighted statement is inconsistent with the document.

Return in JSON format with `consistency` and a `reason` for the given choice.

Document: 
{premise}
Summary: 
{hypothesis}
"""

def format_prompt(prompt, premise: str, hypothesis: str, cls=ChatMessage):
    messages = [
        cls(
            role="user", 
            content=prompt.format(premise=premise, hypothesis=hypothesis)
        )
    ]
    return messages

premise, hypothesis, target = train_ds[1]['premise'], train_ds[1]['hypothesis'], train_ds[1]['target']
messages=format_prompt(prompt, premise, hypothesis)

output = call_mistral(model="open-mistral-7b", messages=messages)

output

target

class MistralModel(weave.Model):
    model: str
    prompt: str
    temperature: float = 0.7
    
    @weave.op
    def create_messages(self, premise:str, hypothesis:str):
        return format_prompt(self.prompt, premise, hypothesis)

    @weave.op
    def predict(self, premise:str, hypothesis:str):
        messages = self.create_messages(premise, hypothesis)
        return call_mistral(model=self.model, messages=messages, temperature=self.temperature)

model_7b = MistralModel(model="open-mistral-7b", prompt=prompt, temperature=0.7)
output = model_7b.predict(premise, hypothesis)
Eval
Let's evaluate the model on the validation split of the dataset


def accuracy(model_output, target):
    class_model_output = model_output.get('consistency') if model_output else None
    return {"accuracy": class_model_output == target}

class BinaryMetrics(weave.Scorer):
    class_name: str
    eps: float = 1e-8

    @weave.op()
    def summarize(self, score_rows) -> dict:
        # filter out None rows, model may error out sometimes...
        score_rows = [score for score in score_rows if score["correct"] is not None]
        # Compute f1, precision, recall
        tp = sum([not score["negative"] and score["correct"] for score in score_rows])
        fp = sum([not score["negative"] and not score["correct"] for score in score_rows])
        fn = sum([score["negative"] and not score["correct"] for score in score_rows])
        precision = tp / (tp + fp + self.eps)
        recall = tp / (tp + fn + self.eps)
        f1 = 2 * precision * recall / (precision + recall + self.eps)
        result = {"f1": f1, "precision": precision, "recall": recall}
        return result

    @weave.op()
    def score(self, target: dict, model_output: dict) -> dict:
        class_model_output = model_output.get(self.class_name) if model_output else None  # 0 or 1
        result = {
            "correct": class_model_output == target,
            "negative": not class_model_output,
        }
        return result

F1 = BinaryMetrics(class_name="consistency")

evaluation = weave.Evaluation(dataset=val_ds, scorers=[accuracy, F1])
7B

await evaluation.evaluate(model_7b)


Iterate a bit on the prompt...
Let's try adding the example from Eugene's blog:


prompt_example = """You are an expert to detect factual inconsistencies and hallucinations. You will be given a document and a summary.
- Carefully read the full document and the provided summary.
- Identify Factual Inconsistencies: any statements in the summary that are not supported by or contradict the information in the document.
Factually Inconsistent: If any statement in the summary is not supported by or contradicts the document, label it as 0
Factually Consistent: If all statements in the summary are supported by the document, label it as 1

Here you have an example:

Document: 
Vehicles and pedestrians will now embark and disembark the Cowes ferry separately following Maritime and Coastguard Agency (MCA) guidance. 
Isle of Wight Council said its new procedures were in response to a resident’s complaint. Councillor Shirley Smart said it would 
“initially result in a slower service”. Originally passengers and vehicles boarded or disembarked the so-called “floating bridge” at the same time. 
Ms Smart, who is the executive member for economy and tourism, said the council already had measures in place to control how passengers 
and vehicles left or embarked the chain ferry “in a safe manner”. However, it was “responding” to the MCA’s recommendations “following this 
complaint”. She added: “This may initially result in a slower service while the measures are introduced and our customers get used to 
the changes.” The service has been in operation since 1859.

Inconsistent summary: A new service on the Isle of Wight’s chain ferry has been launched following a complaint from a resident.

Consistent summary: Passengers using a chain ferry have been warned crossing times will be longer because of new safety measures.

Highlight or list the specific statements in the summary that are inconsistent.
Provide a brief explanation of why each highlighted statement is inconsistent with the document.

Return in JSON format with `consistency` and a `reason` for the given choice.

Document: 
{premise}
Summary: 
{hypothesis}
"""

model_7b_ex = MistralModel(model="open-mistral-7b", prompt=prompt_example, temperature=0.7)
output = model_7b_ex.predict(premise, hypothesis)

output
This is a hard dataset!


await evaluation.evaluate(model_7b_ex)
Large

model_large = MistralModel(model="mistral-large-latest", prompt=prompt_example, temperature=0.7)
await evaluation.evaluate(model_large)


This model is considerably better! over 80% accuracy is great on this hard task 😎

Fine-Tune FTW
Let's see if fine-tuning improves this.


ft_prompt = """You are an expert to detect factual inconsistencies and hallucinations. You will be given a document and a summary.
- Carefully read the full document and the provided summary.
- Identify Factual Inconsistencies: any statements in the summary that are not supported by or contradict the information in the document.
Factually Inconsistent: If any statement in the summary is not supported by or contradicts the document, label it as 0
Factually Consistent: If all statements in the summary are supported by the document, label it as 1

Return in JSON format with `consistency` for the given choice.

Document: 
{premise}
Summary: 
{hypothesis}
"""

answer = """{{"consistency": {label}}}"""  # <- json schema
You will need to format your prompts slightly different for FT

instead of ChatMessage use a dict
Add the output

def format_prompt_ft(row, cls=dict, with_answer=True):
    "Format on the expected MistralAI fine-tuning dataset"
    premise = row['premise']
    hypothesis = row['hypothesis']
    messages = [
        cls(
            role="user", 
            content=prompt.format(premise=premise, hypothesis=hypothesis)
        )
    ]
    if with_answer:
        label = row['target']
        messages.append(
            cls(
                role="assistant",
            content=answer.format(label=label)
            )
        )
    return messages

format_prompt_ft(train_ds[0])
You could use other fancy datasets or pandas, but this is a small dataset so let's not add more complexity...


formatted_train_ds = [format_prompt_ft(row) for row in train_ds]
formatted_val_ds = [format_prompt_ft(row) for row in val_ds]

def save_jsonl(ds, path):
    with open(path, "w") as f:
        for row in ds:
            f.write(json.dumps(row) + "\n")
save_jsonl(formatted_train_ds, DATA_PATH/"formatted_fib_train.jsonl")
save_jsonl(formatted_val_ds, DATA_PATH/"formatted_fib_val.jsonl")
Upload dataset

import os
from mistralai.client import MistralClient

api_key = os.environ.get("MISTRAL_API_KEY")
client = MistralClient(api_key=api_key)

with open(DATA_PATH/"formatted_fib_train.jsonl", "rb") as f:
    ds_train = client.files.create(file=("formatted_df_train.jsonl", f))
with open(DATA_PATH/"formatted_fib_val.jsonl", "rb") as f:
    ds_eval = client.files.create(file=("eval.jsonl", f))

import json
def pprint(obj):
    print(json.dumps(obj.dict(), indent=4))

pprint(ds_train)
Create a fine-tuning job
Ok, now let's create a fine-tune job with the mistral api. Some thing to know:

You only have 2 parameters to play wtih: training_steps and learning_rate
You can use dry_run=True to get an estimate cost
training_steps is not exactly linked to epochs in a direct way, they have a rule of thumbs on the docs. If you do a dry run the epochs will be calculated for you.
We want to run for 10 epochs to reproduce Eugene's results.


from mistralai.models.jobs import TrainingParameters, WandbIntegrationIn

created_jobs = client.jobs.create(
    # dry_run=True,
    model="open-mistral-7b",
    training_files=[ds_train.id],
    validation_files=[ds_eval.id],
    hyperparameters=TrainingParameters(
        training_steps=35,
        learning_rate=0.0001,
        ),
    integrations=[
        WandbIntegrationIn(
            project=PROJECT_NAME,
            run_name="mistral_7b_fib",
            api_key=os.environ.get("WANDB_API_KEY"),
        ).dict()
    ],
)

pprint(created_jobs)

import time

retrieved_job = client.jobs.retrieve(created_jobs.id)
while retrieved_job.status in ["RUNNING", "QUEUED"]:
    retrieved_job = client.jobs.retrieve(created_jobs.id)
    pprint(retrieved_job)
    print(f"Job is {retrieved_job.status}, waiting 10 seconds")
    time.sleep(10)


Use a fine-tuned model
Let's compute the predictions using the fine-tuned 7B model


jobs = client.jobs.list()

retrieved_job = jobs.data[0]

retrieved_job.fine_tuned_model

mistral_7b_ft = MistralModel(prompt=ft_prompt, model=retrieved_job.fine_tuned_model)

await evaluation.evaluate(mistral_7b_ft)
quite substantial improvement! Some take aways:

the Mistral 7B is a much more powerful model than the original Bart that eugene was using on his blog post
With a relatively small high quality dataset the improvements for this downstream task are enormous!
Now we can leverage a faster and cheaper 7B instead of taping into mistral-large. Of course we could have some filtering logic to decide when to use the big gun anyway.
Pre-finetuning on USB to improve performance on FIB
The Unified Summarization Benchmark (USB) is made up of eight summarization tasks including abstractive summarization, evidence extraction, and factuality classification. While FIB documents are based on news, USB documents are based on a different domain—Wikipedia. Labels for factual consistency were created based on edits to summary sentences; inconsistent and consistent labels were assigned to the before and after versions respectively. Here’s the first sample in the dataset:

Check Eugene's Analysis here

Let's mix the USB dataset in the training data...


train_ds_usb = read_jsonl(DATA_PATH / "usb-train.jsonl")

formatted_train_usb_ds = [format_prompt_ft(row) for row in train_ds_usb]
save_jsonl(formatted_train_usb_ds, DATA_PATH/"formatted_train_usb.jsonl")

with open(DATA_PATH/"formatted_train_usb.jsonl", "rb") as f:
    ds_train_usb = client.files.create(file=("formatted_df_train_usb.jsonl", f))

from mistralai.models.jobs import TrainingParameters, WandbIntegrationIn

created_jobs = client.jobs.create(
    # dry_run=True,
    model="open-mistral-7b",
    training_files=[ds_train.id, ds_train_usb.id], # <- just add this new file
    validation_files=[ds_eval.id],
    hyperparameters=TrainingParameters(
        training_steps=200,
        learning_rate=0.0001,
        ),
    integrations=[
        WandbIntegrationIn(
            project=PROJECT_NAME,
            run_name="mistral_7b_fib_usb", # <- change the run name
            api_key=os.environ.get("WANDB_API_KEY"),
        ).dict()
    ],
)

jobs = client.jobs.list()

created_jobs = jobs.data[1]

pprint(created_jobs)

retrieved_job = client.jobs.retrieve(created_jobs.id)

retrieved_job.fine_tuned_model

mistral_7b_usb_ft = MistralModel(prompt=ft_prompt, model=retrieved_job.fine_tuned_model)

await evaluation.evaluate(mistral_7b_usb_ft)
Final results
The fine-tuned model over USB + FIB is now 90%+ accurate!

