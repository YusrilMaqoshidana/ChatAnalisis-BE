import sys
from sentence_transformers import SentenceTransformer

def main():
    print("Warming up SentenceTransformer model: indolem/indobertweet-base-uncased...")
    try:
        model = SentenceTransformer("indolem/indobertweet-base-uncased")
        print("Model loaded/downloaded successfully!")
    except Exception as e:
        print(f"Error loading model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
