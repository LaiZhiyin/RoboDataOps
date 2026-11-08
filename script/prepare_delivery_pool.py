"""Build an offline held-out pool from already downloaded, pinned public shards."""

import json
from pathlib import Path

import pyarrow.parquet as pq

from robodataops.fetch import bundle_analysis_cache
from robodataops.ingest import data_relative_path, file_sha256, load_batch, read_metadata
from robodataops.models import canonical_json


def main():
    project = Path(__file__).resolve().parents[1]
    raw = project / "data/raw/libero"
    base = load_batch(project / "data/public_sample")
    info, _, metadata = read_metadata(raw)
    mapping = {}
    for path in sorted((raw / "data").rglob("*.parquet")):
        for row in pq.read_table(path, columns=["episode_index", "task_index"]).to_pylist():
            mapping.setdefault(row["episode_index"], set()).add(str(row["task_index"]))
    selected, original = [], {ep.episode_index for ep in base.episodes}
    for task in sorted({ep.task_id for ep in base.episodes}):
        candidates = sorted(i for i, ids in mapping.items() if ids == {task} and i not in original)
        if len(candidates) < 4:
            raise ValueError("Not enough held-out complete episodes")
        selected.extend(candidates[:4])
    paths = {data_relative_path(info, m) for m in metadata if m["episode_index"] in selected}
    tracked = [p for p in (raw / "meta").rglob("*") if p.is_file()] + [raw / p for p in paths]
    manifest = {
        **base.manifest,
        "selected_episode_ids": sorted(selected),
        "files": {str(p.relative_to(raw)): file_sha256(p) for p in tracked},
        "video_evidence": {},
        "video_status": "not_fetched",
        "sampling": "four held-out episodes per baseline task; reserved public simulation data, not newly collected delivery",
    }
    # Use a staging manifest; never replace the source acquisition manifest.
    staging = project / "data/derived/delivery-staging"
    staging.mkdir(parents=True, exist_ok=True)
    import shutil

    for relative in manifest["files"]:
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(raw / relative, target)
    (staging / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
    destination = project / "data/public_delivery"
    bundle_analysis_cache(staging, destination)
    shutil.copyfile(
        project / "data/public_sample/LICENSE.apache-2.0.txt",
        destination / "LICENSE.apache-2.0.txt",
    )
    (destination / "NOTICE.md").write_text(
        "# Reserved public delivery simulation pool\n\nSource: https://huggingface.co/datasets/lerobot/libero, revision "
        + base.revision
        + ". Apache-2.0 as declared by the dataset card; license copy included. Original authors retain attribution and rights.\n\nTwenty held-out complete episodes, four per baseline task, disjoint from public_sample. Reserved public simulation data for offline incoming-delivery demonstration, not actual new capture or vendor delivery. Original metadata/shards preserved; manifest selects IDs and SHA256. No videos included. Not a reindexed training split. RoboDataOps code is separately MIT licensed.\n",
        encoding="utf-8",
    )
    print(json.dumps({"episodes": len(load_batch(destination).episodes), "selected": selected}))


if __name__ == "__main__":
    main()
