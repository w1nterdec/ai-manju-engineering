"""Offline audit reproductions. Synthetic files only; never real media/credentials."""
import argparse
from datetime import date
import subprocess
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from manju.adapters import load_config
from manju.assets import AssetStore
from manju.build import compile_episode
from manju.business import load_profile, new_project
from manju.delivery import package, verify_package
from manju.execution import Engine
from manju.io import digest, read_json, write_json
from manju.planning import make_plan

SOURCE = ROOT / 'examples/midnight_letter/episode.json'


def interrupted_blob(root):
    source = root / 'synthetic-reference.txt'
    source.write_bytes(b'AUDIT SYNTHETIC ASSET, NO REAL PERSON OR LICENSE')
    store = AssetStore(root / 'assets')
    metadata = {'source': 'synthetic audit fixture', 'mock': True}

    def interrupt(source_stream, target_stream):
        target_stream.write(source_stream.read(4))
        raise OSError('simulated interrupted copy')

    with patch('manju.assets.shutil.copyfileobj', side_effect=interrupt):
        try:
            store.add(source, 'identity', metadata)
        except OSError:
            pass
    blob = store.root / 'blobs' / digest(source)
    corrupted = blob.exists() and digest(blob) != digest(source)
    try:
        store.add(source, 'identity', metadata)
        retry_blocked = False
    except ValueError:
        retry_blocked = True
    return {'id': 'A1', 'reproduced': corrupted and retry_blocked, 'partial_blob_persisted': corrupted, 'retry_blocked': retry_blocked}


def profile_collision(root):
    profile = load_profile('series_drama')
    profile['templates']['production.json'] = {'audit_fixture': True}
    path = root / 'custom-profile.json'
    write_json(path, profile)
    output = root / 'project'
    new_project(str(path), output)
    overwritten = read_json(output / 'production.json') == {'audit_fixture': True}
    try:
        load_config(output / 'production.json')
        rejected = False
    except ValueError:
        rejected = True
    return {'id': 'A2', 'reproduced': overwritten and rejected, 'core_config_overwritten': overwritten, 'generated_config_invalid': rejected}


def additional_asset_invalidation(root):
    bundle = root / 'bundle'
    compile_episode(SOURCE, bundle)
    store = AssetStore(root / 'assets')
    ids = []
    for variant in ('A', 'B'):
        path = root / f'product-{variant}.txt'
        path.write_text('SYNTHETIC PRODUCT REFERENCE ' + variant, encoding='utf-8')
        record = store.add(path, 'product', {'source': 'synthetic audit fixture', 'mock': True})
        ids.append(store.approve(record['asset_id'], 'AUDIT_FIXTURE', 'synthetic technical fixture, not commercial rights')['asset_id'])
    config = load_config()
    config.update(asset_store=str(store.root), additional_assets=[ids[0]])
    before = make_plan(bundle, config)
    engine = Engine(root / 'run', config)
    try:
        engine.run(before, auto_review_mock=True)
        config['additional_assets'] = [ids[1]]
        after = make_plan(bundle, config)
        engine.sync(after)
        stale = [key for key, row in engine.state().items() if row['state'] == 'stale']
    finally:
        engine.close()
    old = {task['id']: task['key'] for task in before['tasks']}
    new = {task['id']: task['key'] for task in after['tasks']}
    return {'id': 'A3', 'reproduced': before['plan_id'] != after['plan_id'] and old == new and not stale, 'plan_changed': before['plan_id'] != after['plan_id'], 'task_keys_unchanged': old == new, 'stale_tasks': stale}


def stale_package_lineage(root):
    bundle = root / 'bundle'
    compile_episode(SOURCE, bundle)
    config = load_config()
    engine = Engine(root / 'run', config)
    try:
        status = engine.run(make_plan(bundle, config), auto_review_mock=True)
    finally:
        engine.close()
    output_record = json.loads(status['tasks']['image:S001']['result'])
    artifact = root / 'run/artifacts' / output_record['path']
    artifact.write_bytes(b'{"audit_replacement":true}')
    output = root / 'delivery'
    package(bundle, output, config, run=root / 'run', demo=True)
    outer = verify_package(output)
    lineage_mismatch = digest(output / 'media' / artifact.name) != output_record['sha256']
    return {'id': 'A4', 'reproduced': outer['passed'] and lineage_mismatch, 'demo_package_accepted': True, 'outer_integrity_passed': outer['passed'], 'lineage_content_mismatch': lineage_mismatch, 'scope': 'mock package only; no actual production bypass demonstrated'}


def main():
    parser = argparse.ArgumentParser(description='Historical offline audit observations, not a defect-acceptance CI test')
    parser.add_argument('--as-of', default=date.today().isoformat())
    parser.add_argument('--out')
    args = parser.parse_args()
    date.fromisoformat(args.as_of)
    if args.out and Path(args.out).exists():
        raise ValueError('Audit evidence exists; choose a new version')
    results = []
    for operation in (interrupted_blob, profile_collision, additional_asset_invalidation, stale_package_lineage):
        with tempfile.TemporaryDirectory(prefix='manju-audit-') as directory:
            results.append(operation(Path(directory)))
    try:
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        head = None
    from manju import __version__
    modules = ('assets', 'business', 'planning', 'delivery', 'adapters', 'execution', 'costs', 'safeio')
    summary = {'audit_version': '1.0', 'as_of': args.as_of, 'subject_version': __version__, 'subject_git_head': head, 'mock_only': True, 'source_fingerprints': {f'manju/{name}.py': digest(ROOT / 'manju' / f'{name}.py') for name in modules}, 'results': results, 'notice': 'Historical audit observations; no real media generation, rights approval or credentials. Convert these scenarios to regression assertions when fixing.'}
    if args.out:
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
