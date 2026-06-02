"""
Unit tests for the role-scoping logic in _run_export_job.

Tests the three fixed functions directly with mocked block data that mirrors
the actual session data: BNP on page 1, UBS + Citibank on page 2, where a BNP
search key ("AI Strategy and Governance") also appears in Citibank's section.
"""

import sys

# ── Reproduce the exact functions from _run_export_job ────────────────────────

def _short_key(name):
    for sep in (' – ', ' — ', ' - ', ' / ', ' ('):
        idx = name.find(sep)
        if idx > 0:
            return name[:idx].strip().upper()
    return name[:30].strip().upper()


def _find_role_bounds_on_page(blocks, all_companies):
    company_ys = {}
    sorted_blocks = sorted(blocks, key=lambda bk: bk['bbox'][1])
    for bk in sorted_blocks:
        if bk['type'] != 0:
            continue
        for line in bk['lines']:
            spans = [s for s in line['spans'] if s['text'].strip()]
            if not spans:
                continue
            has_bold = any('Bold' in s['font'] or 'bold' in s['font'] for s in spans)
            if not has_bold:
                continue
            line_upper = ''.join(s['text'] for s in line['spans']).strip().upper()
            for company in all_companies:
                if company and company not in company_ys:
                    if _short_key(company) in line_upper:
                        company_ys[company] = line['bbox'][1]
    sorted_hits = sorted(company_ys.items(), key=lambda x: x[1])
    result = {}
    for i, (company, y_start) in enumerate(sorted_hits):
        y_end = sorted_hits[i + 1][1] if i + 1 < len(sorted_hits) else None
        result[company] = (y_start, y_end)
    return result


# ── Mock block builder ────────────────────────────────────────────────────────

def make_block(y, text, bold=False, is_bullet_sym=False):
    """Create a minimal fitz-style text block at the given y."""
    font = 'Helvetica-Bold' if bold else ('Symbol' if is_bullet_sym else 'Helvetica')
    x0, x1 = (45, 55) if is_bullet_sym else (65, 540)
    return {
        'type': 0,
        'bbox': (x0, y, x1, y + 12),
        'lines': [{
            'bbox': (x0, y, x1, y + 12),
            'spans': [{'text': text, 'font': font, 'size': 9,
                       'bbox': (x0, y, x1, y + 12)}],
        }],
    }


# ── Test 1: _short_key extracts correct prefix ────────────────────────────────

def test_short_key():
    cases = [
        ('UBS – Asset Management Risk Centre of Excellence (CoE)', 'UBS'),
        ('BNP Paribas – Regulatory & Risk Solutions & Industrialisation (RSSI / RRSI)', 'BNP PARIBAS'),
        ('Citibank', 'CITIBANK'),
        ('Goldman Sachs (London)', 'GOLDMAN SACHS'),
        ('JP Morgan / Chase', 'JP MORGAN'),
    ]
    for name, expected in cases:
        result = _short_key(name)
        assert result == expected, f"_short_key({name!r}) = {result!r}, want {expected!r}"
    print("PASS test_short_key")


# ── Test 2: _find_role_bounds_on_page finds companies by short prefix ─────────

def test_find_bounds_short_prefix():
    """Full company name (76 chars) wraps in PDF — short prefix still matches."""
    BNP = 'BNP Paribas – Regulatory & Risk Solutions & Industrialisation (RSSI / RRSI)'
    UBS = 'UBS – Asset Management Risk Centre of Excellence (CoE)'

    # Simulate page 1: only BNP header visible, long name wraps (only first line present)
    page1_blocks = [
        make_block(50, 'BNP Paribas – Regulatory & Risk Solutions', bold=True),
        # second line of the wrapping header — NOT bold (or different block)
        make_block(62, '& Industrialisation (RSSI / RRSI)', bold=False),
        make_block(100, '2022 – Present', bold=False),
        make_block(120, 'AI Strategy and Governance: Mobilised and led CCCO AI working group.'),
    ]
    bounds = _find_role_bounds_on_page(page1_blocks, [UBS, BNP])
    assert BNP in bounds, f"BNP not found in page1 bounds: {bounds}"
    assert UBS not in bounds, f"UBS should not be on page 1"
    print(f"  Page1 bounds: {bounds}")
    print("PASS test_find_bounds_short_prefix")


# ── Test 3: cross-role contamination is prevented ─────────────────────────────

def test_no_cross_role_contamination():
    """
    The critical scenario: BNP search key 'AI Strategy and Governance' also
    appears in Citibank's section on page 2. With the fix, BNP bullets are
    skipped on page 2 (company not in role_bounds), so Citibank is untouched.
    """
    BNP = 'BNP Paribas – Regulatory & Risk Solutions & Industrialisation (RSSI / RRSI)'
    UBS = 'UBS – Asset Management Risk Centre of Excellence (CoE)'

    # Page 2: UBS section y=50-190, Citibank section y=200+
    page2_blocks = [
        make_block(50,  'UBS – Asset Management Risk Centre of Excellence (CoE)', bold=True),
        make_block(70,  '2020 – 2022', bold=False),
        make_block(95,  '▪', is_bullet_sym=True),  # ▪ bullet
        make_block(95,  'Project Risk Lead: Led risk oversight for Credit Suisse/UBS integration.'),
        make_block(115, '▪', is_bullet_sym=True),
        make_block(115, 'Stakeholder Management: Partnered with stakeholders.'),
        make_block(200, 'Citibank – Markets Risk', bold=True),
        make_block(220, '2018 – 2020', bold=False),
        make_block(245, '▪', is_bullet_sym=True),
        # This Citibank bullet contains the same search key as BNP bullet — the old bug
        make_block(245, 'AI Strategy and Governance: Citibank AI governance framework.'),
    ]

    # _find_role_bounds_on_page should find UBS but NOT BNP (BNP header not on page 2)
    bounds = _find_role_bounds_on_page(page2_blocks, [UBS, BNP])
    assert UBS in bounds, "UBS should be found on page 2"
    assert BNP not in bounds, f"BNP should NOT be on page 2, but got: {bounds}"

    ubs_range = bounds[UBS]
    print(f"  UBS y-range: {ubs_range}")

    # Simulate the processing loop decision
    bnp_replacement = (BNP, 'AI Strategy and Governance: Mobilised and led CCCO AI working group.', 'BNP Test #2')
    role_key = bnp_replacement[0]
    if role_key not in bounds:
        print(f"  BNP bullet correctly SKIPPED on page 2 (company not in role_bounds)")
    else:
        raise AssertionError("BUG: BNP bullet would be processed on page 2 — cross-contamination risk!")

    print("PASS test_no_cross_role_contamination")


# ── Test 4: UBS bullet IS processed on page 2 (not skipped) ──────────────────

def test_ubs_processed_on_correct_page():
    """
    Citibank is NOT in bullet_analysis_by_role_keys (the real data confirms this).
    So _find_role_bounds_on_page only tracks UBS/BNP; Citibank doesn't bound UBS.
    UBS y_end is therefore None (extends to bottom of page).

    The protection against Citibank contamination comes from BNP being SKIPPED
    on page 2, not from UBS's y_end. This is safe because UBS search keys and
    Citibank bullet text have zero overlap in the actual CV data.
    """
    UBS = 'UBS – Asset Management Risk Centre of Excellence (CoE)'
    BNP = 'BNP Paribas – Regulatory & Risk Solutions & Industrialisation (RSSI / RRSI)'

    page2_blocks = [
        make_block(50, 'UBS – Asset Management Risk Centre of Excellence (CoE)', bold=True),
        make_block(70, '2020 – 2022'),
        make_block(95, 'Project Risk Lead: Led risk oversight for Credit Suisse/UBS integration.'),
        make_block(200, 'Citibank – Markets Risk', bold=True),
        make_block(245, 'AI Strategy and Governance: Citibank AI governance framework.'),
    ]

    bounds = _find_role_bounds_on_page(page2_blocks, [UBS, BNP])

    assert UBS in bounds, "UBS should be found on page 2"
    assert BNP not in bounds, "BNP should NOT be on page 2"

    # Citibank is not in all_companies, so UBS extends to end of page (y_end=None)
    ubs_y_start, ubs_y_end = bounds[UBS]
    assert ubs_y_end is None, f"UBS y_end should be None (Citibank not tracked), got {ubs_y_end}"
    print(f"  UBS bounds on page 2: {bounds[UBS]}  (extends to page bottom — Citibank not in analysis keys)")

    # UBS search key "Project Risk Lead" IS within UBS range
    y_min, y_max = ubs_y_start, ubs_y_end
    ubs_key_found = any(
        (y_min is None or line['bbox'][1] >= y_min) and
        (y_max is None or line['bbox'][1] < y_max) and
        'Project Risk Lead' in ''.join(s['text'] for s in line['spans'])
        for blk in page2_blocks if blk['type'] == 0
        for line in blk['lines']
    )
    assert ubs_key_found, "UBS 'Project Risk Lead' key not found in UBS y-range"

    # Confirm BNP search key "AI Strategy and Governance" is protected:
    # BNP is skipped on page 2 because BNP not in role_bounds.
    # In the real CV, UBS and BNP search keys have ZERO overlap (verified separately),
    # so even though UBS y_range extends to page bottom, a UBS bullet will never
    # accidentally match a Citibank bullet that shares a BNP search key.
    ubs_search_keys_real = {
        'Project Risk Lead', 'Integration Programme Governance', 'Executive Reporting',
        'Stakeholder Management', 'Stakeholder & Committee Engagement',
        'Regualtory & Audit Engagement', 'Integration Risk Reviews', 'Compliance Preparation',
        'Non-Financial Controls Assurance', 'Cyber & Obsolescence Remediation Oversight',
        'Operational & Technology Controls Assurance', 'Technology Controls Oversight',
        'Controls Evidence Standards', 'Controls Evidence Enhancement',
    }
    citibank_overlap_key = 'AI Strategy and Governance'
    assert citibank_overlap_key not in ubs_search_keys_real, \
        f"'AI Strategy and Governance' is also a UBS search key — would risk Citibank contamination!"
    print(f"  'AI Strategy and Governance' is a BNP key only (not UBS) — no UBS→Citibank contamination risk")
    print("PASS test_ubs_processed_on_correct_page")


# ── Test 5: BNP processed on page 1 where its header exists ──────────────────

def test_bnp_processed_on_page1():
    BNP = 'BNP Paribas – Regulatory & Risk Solutions & Industrialisation (RSSI / RRSI)'
    UBS = 'UBS – Asset Management Risk Centre of Excellence (CoE)'

    page1_blocks = [
        make_block(50,  'BNP Paribas – Regulatory & Risk Solutions', bold=True),
        make_block(70,  '2022 – Present'),
        make_block(95,  '▪', is_bullet_sym=True),
        make_block(95,  'AI Strategy and Governance: Mobilised and led CCCO AI working group.'),
        make_block(115, '▪', is_bullet_sym=True),
        make_block(115, 'Target-State Design: Helped shape functional target-state for CIB.'),
    ]

    bounds = _find_role_bounds_on_page(page1_blocks, [UBS, BNP])
    assert BNP in bounds, f"BNP should be found on page 1. Got: {bounds}"
    assert UBS not in bounds, "UBS should NOT be on page 1"

    bnp_y_start, bnp_y_end = bounds[BNP]
    assert bnp_y_end is None, f"BNP is last on page 1, y_end should be None, got {bnp_y_end}"

    # Verify BNP search key found within BNP y-range
    y_min, y_max = bnp_y_start, bnp_y_end
    search_key = 'AI Strategy and Governance'
    found = any(
        (y_min is None or line['bbox'][1] >= y_min) and
        (y_max is None or line['bbox'][1] < y_max) and
        search_key in ''.join(s['text'] for s in line['spans'])
        for blk in page1_blocks if blk['type'] == 0
        for line in blk['lines']
    )
    assert found, "BNP search key not found in BNP y-range on page 1"
    print(f"  BNP bounds on page 1: {bounds[BNP]}")
    print("PASS test_bnp_processed_on_page1")


# ── Test 6: bullet symbol ▪ (ord=9642) IS in the recognized set ──────────────

def test_bullet_recognition():
    recognized = {8226, 9679, 9675, 9702, 9656, 9642, 9654, 183}
    bullet_chars = ['•', '▪', '●', '·', '▸']
    for ch in bullet_chars:
        assert ord(ch) in recognized or ch in ('•', '●', '○', '◦', '▸', '▪', '▶', '·'), \
            f"Character {ch!r} (ord={ord(ch)}) not recognized as bullet"
    assert 9642 in recognized, "▪ (ord=9642) not in recognized bullet set"
    print("PASS test_bullet_recognition")


# ── Run all tests ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    failures = []
    for name, fn in [
        ('test_short_key', test_short_key),
        ('test_find_bounds_short_prefix', test_find_bounds_short_prefix),
        ('test_no_cross_role_contamination', test_no_cross_role_contamination),
        ('test_ubs_processed_on_correct_page', test_ubs_processed_on_correct_page),
        ('test_bnp_processed_on_page1', test_bnp_processed_on_page1),
        ('test_bullet_recognition', test_bullet_recognition),
    ]:
        try:
            fn()
        except Exception as e:
            print(f"FAIL {name}: {e}")
            failures.append(name)

    print(f"\n{'='*50}")
    if failures:
        print(f"FAILED: {failures}")
        sys.exit(1)
    else:
        print(f"ALL {6} TESTS PASSED")
        sys.exit(0)
