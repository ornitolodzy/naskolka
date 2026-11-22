from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _report(svc) -> None:
    data = svc.campaigns()
    for c in data["campaigns"]:
        lamp = c.get("max_lamp") or {}
        print(f"\n[{c['id']}] {c['name']}  (materiały: {', '.join(c['members'])}; spójność: {c['cohesion']}; "
              f"rodzina: {c.get('family')}; lampka: {lamp.get('color')})")
        for s in c["signature"][:8]:
            print(f"    - {s['label']}: {s['value']}  [{s['members']} mat., waga {s['weight']}]")
    if data["families"]:
        print("\nRodziny kampanii:")
        for f in data["families"]:
            print(f"  {f['id']}: {', '.join(f['campaigns'])}")
    model = svc.model()
    print("\nNajsilniejsze powiązania:")
    for p in sorted(model.pairs.values(), key=lambda p: -p.score)[:15]:
        top = "; ".join(f"{e.feature}={e.value[:40]}" for e in p.evidence[:3])
        print(f"  {p.a:>7} - {p.b:<7} {p.score:.2f} {p.relation:<9} {top}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kolekcjoner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("import")
    imp.add_argument("--path", default=None)
    sub.add_parser("report")
    sub.add_parser("models")
    sd = sub.add_parser("seed")
    sd.add_argument("--shards", type=int, default=3)
    sub.add_parser("train")
    sub.add_parser("reprocess")
    args = ap.parse_args(argv)

    if args.cmd == "models":
        from .features import asr, clip, faces

        ok_faces = faces.ensure_models()
        ok_clip = clip.ensure_model()
        ok_asr = asr._model() is not None if asr.available() else False
        print("modele twarzy:", "OK" if ok_faces else "BŁĄD")
        print("CLIP:", "OK" if ok_clip else "BŁĄD")
        print(f"Whisper ({asr.info()['model']}, {asr.info()['device']}):", "OK" if ok_asr else "BŁĄD")
        return 0 if ok_faces and ok_clip and ok_asr else 1

    if args.cmd == "seed":
        from . import seed

        print(seed.fetch_openfake(shards=args.shards))
        print(seed.summary())
        return 0

    from .service import Service

    svc = Service()
    if args.cmd == "train":
        import json

        print(json.dumps(svc.train_ai(), ensure_ascii=False, indent=2))
        svc.pool.shutdown(wait=True)
        return 0
    if args.cmd == "reprocess":
        n = svc.reprocess_all()
        print(f"przetwarzam ponownie {n} materiałów...")
        t0 = time.time()
        while any(r["status"] in {"pending", "processing"} for r in svc.store.all(with_features=False)):
            time.sleep(2)
        print(f"gotowe w {time.time() - t0:.0f} s")
    if args.cmd == "import":
        state = svc.import_dataset(Path(args.path) if args.path else None)
        print(f"importuję {state.get('total')} incydentów...")
        t0 = time.time()
        while svc.import_state.get("running"):
            time.sleep(1)
        rows = svc.store.all(with_features=False)
        for r in rows:
            print(f"  {r['id']:<10} {r['status']:<10} {r['error'] or ''}")
        print(f"gotowe w {time.time() - t0:.0f} s")
    _report(svc)
    svc.pool.shutdown(wait=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
