import json
import sys
from pathlib import Path

from maizi.engine import process_orders

def main(args=None):
    source, target = (args or sys.argv[1:])[:2]
    request = json.loads(Path(source).read_text(encoding="utf-8"))
    result = process_orders(request["rows"], request["products"], request["flow"])
    temporary = Path(target).with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)

if __name__ == "__main__":
    main()
