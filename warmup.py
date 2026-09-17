import os
import sys
from sentence_transformers import SentenceTransformer

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_model_path = os.path.join(base_dir, "models", "indobertweet-base-uncased")
    print(f"Warming up SentenceTransformer model. Checking local path: {local_model_path}")
    try:
        if not os.path.exists(local_model_path):
            print("Model not found locally. Downloading from Hugging Face Hub...")
            model = SentenceTransformer("indolem/indobertweet-base-uncased")
            print(f"Saving model to {local_model_path}...")
            model.save(local_model_path)
            print("Model saved successfully!")
        else:
            print("Model already exists locally. Loading model...")
            model = SentenceTransformer(local_model_path)
            print("Local model loaded successfully!")
    except Exception as e:
        print(f"Error during model warmup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
