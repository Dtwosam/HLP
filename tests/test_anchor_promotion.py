import pytest

from hlp.data.anchor_promotion import select_anchor_source_ranges


WETH = "0x" + "11" * 20
USDG = "0x" + "22" * 20
POOL = "0x" + "33" * 20


def _source(lo, hi, *, sha_char="a", records=1, **overrides):
    row = {
        "from_block": lo,
        "to_block": hi,
        "chain_id": 4663,
        "weth": WETH,
        "usdg": USDG,
        "pool": POOL,
        "sha256": sha_char * 64,
        "records": records,
        "source_run_id": 1,
        "source_artifact": f"range-{lo}-{hi}",
        "path": f"/tmp/{lo}-{hi}.jsonl",
    }
    row.update(overrides)
    return row


def _select(rows, *, start=10, head=29):
    return select_anchor_source_ranges(
        rows,
        start_block=start,
        snapshot_head_block=head,
        chain_id=4663,
        weth=WETH,
        usdg=USDG,
        pool=POOL,
    )


def test_anchor_promotion_selects_exact_continuous_ranges():
    rows = [
        _source(20, 29, sha_char="b"),
        _source(10, 19, sha_char="a"),
    ]

    selected = _select(rows)

    assert [(row["from_block"], row["to_block"]) for row in selected] == [
        (10, 19),
        (20, 29),
    ]


def test_anchor_promotion_deduplicates_identical_exact_range():
    first = _source(
        10,
        19,
        source_run_id=2,
        source_artifact="z",
    )
    duplicate = _source(
        10,
        19,
        source_run_id=1,
        source_artifact="a",
    )

    selected = _select(
        [first, duplicate, _source(20, 29, sha_char="b")]
    )

    assert len(selected) == 2
    assert selected[0]["source_run_id"] == 1


def test_anchor_promotion_rejects_conflicting_exact_range():
    with pytest.raises(ValueError, match="conflicting anchor evidence"):
        _select([
            _source(10, 19, sha_char="a"),
            _source(10, 19, sha_char="b"),
            _source(20, 29, sha_char="c"),
        ])


def test_anchor_promotion_rejects_duplicate_record_count_drift():
    with pytest.raises(ValueError, match="conflicting anchor record count"):
        _select([
            _source(10, 19, records=1),
            _source(10, 19, records=2),
            _source(20, 29, sha_char="b"),
        ])


def test_anchor_promotion_rejects_gap():
    with pytest.raises(ValueError, match="promotion gap"):
        _select([
            _source(10, 18),
            _source(20, 29, sha_char="b"),
        ])


def test_anchor_promotion_rejects_overlap():
    with pytest.raises(ValueError, match="promotion overlap"):
        _select([
            _source(10, 20),
            _source(20, 29, sha_char="b"),
        ])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("chain_id", 1, "chain mismatch"),
        ("weth", "0x" + "44" * 20, "WETH mismatch"),
        ("usdg", "0x" + "55" * 20, "USDG mismatch"),
        ("pool", "0x" + "66" * 20, "pool mismatch"),
    ],
)
def test_anchor_promotion_rejects_identity_drift(field, value, message):
    rows = [
        _source(10, 19, **{field: value}),
        _source(20, 29, sha_char="b"),
    ]

    with pytest.raises(ValueError, match=message):
        _select(rows)


def test_anchor_promotion_rejects_incomplete_tail():
    with pytest.raises(ValueError, match="ends at 19, expected 29"):
        _select([_source(10, 19)])
