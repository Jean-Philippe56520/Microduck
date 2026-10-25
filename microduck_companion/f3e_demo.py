"""Show unreviewed public catalog in a metadata-only demo."""
import json
from dataclasses import asdict
from .visual_annotation_review import empty_review_payload, summarize_catalog_reviews
def main():
    result=summarize_catalog_reviews(empty_review_payload())
    print(json.dumps(asdict(result),sort_keys=True))
if __name__=="__main__":
    main()
