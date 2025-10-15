import os, logging
os.environ["OPENAI_THINK_MIN"]="10"
os.environ["OPENAI_MODEL"]="gpt-5"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
from src.translate import _summarize_with_openai
text = "CT HEAD: Normal."
print("has key =", bool(os.getenv("OPENAI_API_KEY")))
print(_summarize_with_openai(text, "English"))
