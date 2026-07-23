import os
import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    BitsAndBytesConfig
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig

MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B"
OUTPUT_DIR = "./patchpilot-lora-v1"

def generate_synthetic_training_data() -> Dataset:
    raw_data = [
        {
            "error_log": "Bandit: B608: Hardcoded SQL string detected.",
            "buggy_code": "def get_user(db, user_id):\n    query = f'SELECT * FROM users WHERE id = {user_id}'\n    return db.execute(query)",
            "patch": "--- a/db.py\n+++ b/db.py\n@@ -1,3 +1,3 @@\n def get_user(db, user_id):\n-    query = f'SELECT * FROM users WHERE id = {user_id}'\n-    return db.execute(query)\n+    query = 'SELECT * FROM users WHERE id = %s'\n+    return db.execute(query, (user_id,))"
        },
        {
            "error_log": "TypeError: Cannot read properties of undefined (reading 'map')",
            "buggy_code": "function renderList(items) {\n    return items.map(i => `<li>${i}</li>`);\n}",
            "patch": "--- a/ui.js\n+++ b/ui.js\n@@ -1,3 +1,3 @@\n function renderList(items) {\n-    return items.map(i => `<li>${i}</li>`);\n+    if (!items || !Array.isArray(items)) return '';\n+    return items.map(i => `<li>${i}</li>`);\n }"
        },
        {
            "error_log": "Out of bounds memory access (Segmentation fault)",
            "buggy_code": "int arr[5];\nfor(int i=0; i<=5; i++) {\n    arr[i] = 0;\n}",
            "patch": "--- a/main.c\n+++ b/main.c\n@@ -1,3 +1,3 @@\n int arr[5];\n-for(int i=0; i<=5; i++) {\n+for(int i=0; i<5; i++) {\n     arr[i] = 0;\n }"
        }
    ]

    formatted = []
    for item in raw_data:
        text = f"""<|im_start|>system
You are PatchPilot, an autonomous security remediation agent. Given an error log and buggy code, output ONLY the unified Git patch. Do not output conversational text.<|im_end|>
<|im_start|>user
Error: {item['error_log']}
Code:
{item['buggy_code']}<|im_end|>
<|im_start|>assistant
````diff
{item['patch']}
```<|im_end|>"""
        formatted.append({"text": text})

    return Dataset.from_list(formatted)


print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
tokenizer.pad_token = tokenizer.eos_token

print("Configuring 4-bit quantization...")
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16
)

print("Loading base model...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    quantization_config=bnb_config,
    torch_dtype=torch.float16,
    device_map="auto"
)
model = prepare_model_for_kbit_training(model)

print("Attaching LoRA adapters...")
peft_config = LoraConfig(
    r=16, 
    lora_alpha=32, 
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], 
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)
model = get_peft_model(model, peft_config)

dataset = generate_synthetic_training_data()

print("Initializing SFT Trainer...")


sft_config = SFTConfig(
    output_dir=OUTPUT_DIR,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    logging_steps=1,
    max_steps=20,
    optim="paged_adamw_8bit",
    fp16=False,
    bf16=False,
    save_strategy="no",
    max_length=1024,              
    dataset_text_field="text",      
    packing=False,
)

trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    # peft_config=peft_config,
    args=sft_config
)

print("Beginning LoRA fine-tuning...")
trainer.train()

print("Saving adapters...")
trainer.model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print("Training Complete!")