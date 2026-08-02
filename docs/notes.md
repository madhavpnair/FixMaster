## Celery
- for the asynchronous execution of the long-running pipeline
- does not wait
- executes in the background

## MCP
- expose tools to LLM
- eg : read_file(), list_directories() etc.
- more tools to be added in the mcp server

## LangChain
- orchestrates the agent workflow and tool-calling process.

## sandbox
- run the code 
- get the logs
- dind (Docker-in-Docker)

## Qdrant
- vector database
- stores and retrieves embeddings for the RAG pipeline.


## Docker
- image is a blueprint to make a container. it acts as a template
- images are downloaded from DockerHub


## fixed issues
- api version issue : v1 vs. v1beta(langchain default) messed up while fetching the model

## PEFT - Parameter Efficient Fine Tuning
- LoRA vs. QLoRA (Quantized Low Rank Adaptation) compresses the base model to lower bit precision
- base model full precision (16-bit) vs. quantized (4 or 8-bit)
    - Represent model weights using fewer bits, so the model uses less memory and runs faster.
- high vram requirement vs. low requirement
- faster training vs. slower
- higher accuracy vs. lower (good for general tasks)

### LoRA
4096 * 4096 parameters --> 4096 * r + r * 4096 trainable parameters

## Datasets
- MITRE CVE


```
     Docker Host
                         │
 ┌───────────────────────┼────────────────────────┐
 │                       │                        │
 ▼                       ▼                        ▼
API Container      Worker Container        Redis Container
(FastAPI)            (Celery)             (Message Broker)
                          │
                          ▼
                  Sandbox Container
                  (Docker-in-Docker)

```
