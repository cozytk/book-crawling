"""Import audited product identifiers, never ratings. Dry run unless --apply.

Use the target store's existing environment credentials. The crawler still
fetches every selected product and validates its current title and author.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api.db import get_client
from api.source_identity import validate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    records=json.loads(Path(args.file).read_text())
    if not isinstance(records,list) or len(records)>1000:
        raise ValueError('Expected at most 1000 audited identity records')
    for record in records:
        if not validate(record,record.get('query',''),record.get('platform')):
            raise ValueError('Invalid, untrusted, or expired product identity')
        if any(key in record for key in ['rating','rating_count','review_count','text_review_count']):
            raise ValueError('Ratings cannot be imported as product identities')
    if args.apply:
        store=get_client()
        if not hasattr(store,'cache_source_identity'):
            raise ValueError('The configured store does not support product identities')
        for record in records:
            store.cache_source_identity(record['query'],record['platform'],record)
    print(json.dumps({'identities':len(records),'applied':args.apply,'ratings_imported':0}))


if __name__=='__main__':
    main()
