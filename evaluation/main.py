"""
Buy or Wait? Evaluation Pipeline
Evaluation workflow against sample_requests.csv and output.csv validation.
"""

import csv
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == 'evaluation' else os.path.dirname(os.path.dirname(BASE_DIR))
CODE_DIR = os.path.join(REPO_ROOT, 'code')

if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

try:
    from engine import FinancialAgent
except ImportError:
    from code.engine import FinancialAgent  # type: ignore[import-not-found]

EXPECTED_COLUMNS = [
    'request_id',
    'amount_safe_to_pay',
    'affordability_status',
    'recommended_payment_method',
    'payment_plan',
    'earliest_date_for_full_payment',
    'spending_changes_needed',
    'decision_explanation'
]

ALLOWED_STATUSES = {
    'affordable_now',
    'affordable_with_plan',
    'affordable_later',
    'not_affordable'
}

ALLOWED_METHODS = {
    'full_payment',
    'partial_payment',
    'installments',
    'wait',
    'not_recommended'
}

def evaluate_samples():
    print("=" * 70)
    print("RUNNING BENCHMARK EVALUATION ON dataset/sample_requests.csv")
    print("=" * 70)

    dataset_dir = os.path.join(REPO_ROOT, 'dataset')
    sample_path = os.path.join(dataset_dir, 'sample_requests.csv')
    agent = FinancialAgent(data_dir=dataset_dir)

    with open(sample_path, encoding='utf-8') as f:
        samples = list(csv.DictReader(f))

    n_samples = len(samples)
    status_correct = 0
    method_correct = 0
    plan_correct = 0
    earliest_correct = 0
    changes_correct = 0
    safe_amt_diffs = []

    print(f"\nEvaluating {n_samples} ground-truth reference requests...\n")
    print(f"{'Req ID':12} {'Status Match':14} {'Method Match':14} {'Plan Match':12} {'Earliest Match':16} {'Safe Amt Diff':14}")
    print("-" * 86)

    for s in samples:
        req_id = s['request_id']
        pred = agent.evaluate_request(s)

        s_match = pred['affordability_status'] == s['affordability_status']
        m_match = pred['recommended_payment_method'] == s['recommended_payment_method']
        p_match = pred['payment_plan'] == s['payment_plan']
        e_match = pred['earliest_date_for_full_payment'] == s['earliest_date_for_full_payment']
        c_match = pred['spending_changes_needed'] == s['spending_changes_needed']

        pred_safe = float(pred['amount_safe_to_pay'])
        gt_safe = float(s['amount_safe_to_pay'])
        diff_safe = abs(pred_safe - gt_safe)
        safe_amt_diffs.append(diff_safe)

        if s_match: status_correct += 1
        if m_match: method_correct += 1
        if p_match: plan_correct += 1
        if e_match: earliest_correct += 1
        if c_match: changes_correct += 1

        print(f"{req_id:12} {str(s_match):14} {str(m_match):14} {str(p_match):12} {str(e_match):16} {diff_safe:14.2f}")

    print("-" * 86)
    print("\nBENCHMARK ACCURACY SUMMARY:")
    print(f"  Affordability Status:            {status_correct}/{n_samples} ({status_correct/n_samples*100:.1f}%)")
    print(f"  Recommended Payment Method:      {method_correct}/{n_samples} ({method_correct/n_samples*100:.1f}%)")
    print(f"  Earliest Date For Full Payment:  {earliest_correct}/{n_samples} ({earliest_correct/n_samples*100:.1f}%)")
    print(f"  Payment Plan Format & Content:   {plan_correct}/{n_samples} ({plan_correct/n_samples*100:.1f}%)")
    print(f"  Spending Changes Needed:         {changes_correct}/{n_samples} ({changes_correct/n_samples*100:.1f}%)")
    print(f"  Mean Safe Amount Absolute Error: {sum(safe_amt_diffs)/len(safe_amt_diffs):.2f}")

def validate_submission_file():
    output_path = os.path.join(REPO_ROOT, 'output.csv')
    requests_path = os.path.join(REPO_ROOT, 'dataset', 'requests.csv')

    print("\n" + "=" * 70)
    print(f"VALIDATING SUBMISSION FILE: {output_path}")
    print("=" * 70)

    if not os.path.exists(output_path):
        print(f"WARNING: output.csv does not exist yet at {output_path}.")
        print("Run 'python code/main.py' to generate output.csv first.")
        return False

    with open(requests_path, encoding='utf-8') as f:
        req_rows = list(csv.DictReader(f))
    req_amounts = {r['request_id']: float(r['requested_amount']) for r in req_rows}

    with open(output_path, encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        rows = list(reader)

    # 1. Header validation
    if header != EXPECTED_COLUMNS:
        print("FAIL: Header columns mismatch!")
        print(f"  Expected: {EXPECTED_COLUMNS}")
        print(f"  Found:    {header}")
        return False
    print(" PASS: Column headers and column order match specification exactly.")

    # 2. Row count validation
    if len(rows) != len(req_rows):
        print(f"FAIL: Row count mismatch! Expected {len(req_rows)}, found {len(rows)}")
        return False
    print(f" PASS: Exact row count matches ({len(rows)} predictions).")

    # 3. Content and bounds validation
    dict_rows = [dict(zip(header, r)) for r in rows]
    errors = []
    for idx, r in enumerate(dict_rows, 1):
        rid = r['request_id']
        req_amt = req_amounts[rid]
        try:
            safe_amt = float(r['amount_safe_to_pay'])
            if not (0 <= safe_amt <= req_amt + 1e-4):
                errors.append(f"Row {idx} ({rid}): amount_safe_to_pay {safe_amt} outside [0, {req_amt}]")
        except ValueError:
            errors.append(f"Row {idx} ({rid}): invalid amount_safe_to_pay '{r['amount_safe_to_pay']}'")

        if r['affordability_status'] not in ALLOWED_STATUSES:
            errors.append(f"Row {idx} ({rid}): invalid status '{r['affordability_status']}'")

        if r['recommended_payment_method'] not in ALLOWED_METHODS:
            errors.append(f"Row {idx} ({rid}): invalid payment method '{r['recommended_payment_method']}'")

    if errors:
        print(f"FAIL: Found {len(errors)} validation errors:")
        for err in errors[:5]:
            print(f"  - {err}")
        return False

    print(" PASS: All values conform to allowed enums and numeric boundary constraints.")
    print(" SUBMISSION VALIDATION PASSED!")
    return True

def main():
    evaluate_samples()
    validate_submission_file()

if __name__ == '__main__':
    main()
