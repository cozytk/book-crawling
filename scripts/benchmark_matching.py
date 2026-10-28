"""Replay the fixed, labeled title corpus against a Git baseline and this tree."""
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cases = json.loads((root / 'tests/fixtures/search-golden.json').read_text())

def measure(source):
    namespace = {}
    exec(compile(source, '<title-matcher>', 'exec'), namespace)
    results = [{**case, 'predicted': bool(namespace['title_score'](case['query'], case['title']))} for case in cases]
    negatives = sum(not row['match'] for row in results)
    positives = len(results) - negatives
    fp = sum(not row['match'] and row['predicted'] for row in results)
    fn = sum(row['match'] and not row['predicted'] for row in results)
    return {'cases':len(results),'positive_cases':positives,'negative_cases':negatives,'false_positives':fp,
            'false_negatives':fn,'false_positive_rate':fp/negatives,'miss_rate':fn/positives,'results':results}

baseline = subprocess.check_output(['git','show','a8466ab:crawlers/utils.py'],cwd=root,text=True)
report = {'kind':'labeled mock corpus; not live-site accuracy','baseline_ref':'a8466ab',
          'before':measure(baseline),'after':measure((root/'crawlers/utils.py').read_text())}
(root/'artifacts').mkdir(exist_ok=True)
(root/'artifacts/matching-benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({name:{k:v for k,v in value.items() if k!='results'} for name,value in report.items() if isinstance(value,dict)},ensure_ascii=False))
