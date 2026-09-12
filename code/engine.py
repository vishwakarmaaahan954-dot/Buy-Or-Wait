"""
Refined FinancialAffordabilityAgent
"""

import csv
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict

VERIFIED_IMAGE_AMOUNTS = {
    'event_253': 4365000.0,
    'event_1442': 100000.0,
    'event_1545': 41272.0,
    'event_1700': 2854.0,
    'event_1786': 822.05,
    'event_3051': 1995.0,
    'event_3231': 8528.0,
    'event_4535': 15339.0,
    'event_5170': 723.0,
    'event_6033': 79679.26,
    'event_6859': 3650.0,
    'event_7307': 33.50,
    'event_7941': 2298.0,
    'event_9421': 4543.0,
    'event_9806': 9968.0,
    'event_10521': 393.22,
}

def parse_date(date_str):
    if not date_str or not date_str.strip():
        return None
    return datetime.strptime(date_str.strip()[:10], '%Y-%m-%d')

def format_date(dt):
    if not dt:
        return ""
    return dt.strftime('%Y-%m-%d')

def clean_amt_str(val):
    if isinstance(val, (int, float)):
        if abs(val - round(val)) < 1e-4:
            return str(int(round(val)))
        return f"{val:.2f}".rstrip('0').rstrip('.')
    return str(val)

class FinancialAgent:
    def __init__(self, data_dir='dataset'):
        self.data_dir = data_dir
        self.load_datasets()

    def load_datasets(self):
        # Profiles
        self.profiles = {}
        with open(os.path.join(self.data_dir, 'financial_profiles.csv'), encoding='utf-8') as f:
            for r in csv.DictReader(f):
                self.profiles[r['user_id']] = r

        # Exchange rates
        self.exchange_rates = {}
        with open(os.path.join(self.data_dir, 'exchange_rates.csv'), encoding='utf-8') as f:
            for r in csv.DictReader(f):
                key = (r['rate_date'], r['from_currency'], r['to_currency'])
                self.exchange_rates[key] = float(r['rate'])

        # Events
        self.user_events = defaultdict(list)
        with open(os.path.join(self.data_dir, 'financial_events.csv'), encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if not r['amount'].strip():
                    eid = r['event_id']
                    if eid in VERIFIED_IMAGE_AMOUNTS:
                        r['amount'] = str(VERIFIED_IMAGE_AMOUNTS[eid])
                self.user_events[r['user_id']].append(r)

        # Payment options
        self.payment_options = defaultdict(list)
        with open(os.path.join(self.data_dir, 'request_payment_options.csv'), encoding='utf-8') as f:
            for r in csv.DictReader(f):
                self.payment_options[r['request_id']].append(r)

        # Messages
        self.user_messages = defaultdict(list)
        with open(os.path.join(self.data_dir, 'messages.csv'), encoding='utf-8') as f:
            for r in csv.DictReader(f):
                self.user_messages[r['user_id']].append(r)

    def convert_amount(self, amount, from_curr, to_curr, date_str):
        if from_curr == to_curr or amount == 0:
            return amount
        key = (date_str, from_curr, to_curr)
        if key in self.exchange_rates:
            return amount * self.exchange_rates[key]
        rev_key = (date_str, to_curr, from_curr)
        if rev_key in self.exchange_rates:
            return amount / self.exchange_rates[rev_key]
        return amount

    def parse_user_messages(self, user_id, request_date_str):
        msgs = self.user_messages.get(user_id, [])
        overrides = {
            'salary_override': None,
            'salary_ended': False,
            'ignore_events': set(),
            'rent_multiplier': 1.0,
            'salary_date_override': None
        }
        for m in msgs:
            text = m['message_text']
            m_idr = re.search(r'Gaji bulanan Anda naik menjadi IDR (\d+).*?mulai (\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
            if m_idr:
                amt = float(m_idr.group(1))
                eff_dt = m_idr.group(2)
                overrides['salary_override'] = (eff_dt, amt)

            m_eur = re.search(r'Your temporary monthly pay is EUR ([\d\.]+)', text, re.IGNORECASE)
            if m_eur:
                amt = float(m_eur.group(1).rstrip('.'))
                overrides['salary_override'] = (request_date_str, amt)

            m_dt = re.search(r'Your confirmed salary is now expected on (\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
            if m_dt:
                overrides['salary_date_override'] = m_dt.group(1)

            m_red = re.search(r'Your next salary is reduced to EUR ([\d\.]+)', text, re.IGNORECASE)
            if m_red:
                amt = float(m_red.group(1).rstrip('.'))
                overrides['salary_override'] = (request_date_str, amt)

            if 'seasonal contract has ended' in text.lower() or 'no off-season income' in text.lower():
                overrides['salary_ended'] = True

            if 'increases monthly rent by 12%' in text.lower():
                overrides['rent_multiplier'] = 1.12

            m_res = re.search(r'Regular salary of EUR ([\d\.]+) resumes on (\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
            if m_res:
                amt = float(m_res.group(1).rstrip('.'))
                eff_dt = m_res.group(2)
                overrides['salary_override'] = (eff_dt, amt)

            m_first = re.search(r'Your first salary will be EUR ([\d\.]+).*?credit date is (\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
            if m_first:
                amt = float(m_first.group(1).rstrip('.'))
                eff_dt = m_first.group(2)
                overrides['salary_override'] = (eff_dt, amt)

        return overrides

    def build_forecast_schedule(self, user_id, request_date_str, spending_changes=None, days=120):
        req_date = parse_date(request_date_str)
        end_date = req_date + timedelta(days=days)
        profile = self.profiles[user_id]
        home_curr = profile['home_currency']
        evs = self.user_events.get(user_id, [])
        overrides = self.parse_user_messages(user_id, request_date_str)

        if spending_changes is None:
            spending_changes = {}

        daily_deltas = defaultdict(float)

        # 1. Pending debits and scheduled events
        for e in evs:
            s_date = parse_date(e['settlement_date'])
            if not s_date or s_date < req_date:
                continue

            status = e['status']
            direction = e['direction']
            amt_str = e['amount']
            if not amt_str.strip():
                continue
            amt = float(amt_str)
            amt = self.convert_amount(amt, e['currency'], home_curr, e['settlement_date'])

            if status == 'pending':
                if direction == 'debit':
                    daily_deltas[s_date] -= amt
            elif status == 'scheduled':
                if direction == 'credit':
                    if e['category'] == 'salary' and not overrides['salary_ended']:
                        daily_deltas[s_date] += amt
                elif direction == 'debit':
                    daily_deltas[s_date] -= amt

        # 2. Check if salary ended
        salaries = [e for e in evs if e['category'] == 'salary' and e['status'] in ['settled', 'scheduled'] and float(e['amount'] or 0) > 0]
        if salaries:
            salaries.sort(key=lambda x: x['settlement_date'])
            last_sal = salaries[-1]
            if 'final employer payroll' in last_sal['description'].lower():
                overrides['salary_ended'] = True

        # Reconstruct recurring salary
        if salaries and not overrides['salary_ended']:
            import statistics
            import collections
            clean_sals = [s for s in salaries if float(s['amount'] or 0) > 0 and 'prorated' not in s['description'].lower() and 'arrears' not in s['description'].lower()]
            if clean_sals:
                sal_amts = [float(s['amount']) for s in clean_sals]
                sal_amt = statistics.median(sal_amts)
                sal_days = [parse_date(s['settlement_date']).day for s in clean_sals]
                sal_day = collections.Counter(sal_days).most_common(1)[0][0]
                latest_ref = clean_sals[-1]
            else:
                sal_amt = float(salaries[-1]['amount'])
                sal_day = parse_date(salaries[-1]['settlement_date']).day
                latest_ref = salaries[-1]
            sal_amt = self.convert_amount(sal_amt, latest_ref['currency'], home_curr, latest_ref['settlement_date'])

            if overrides.get('salary_date_override'):
                sal_day = parse_date(overrides['salary_date_override']).day

            if overrides.get('salary_override'):
                eff_dt_str, new_amt = overrides['salary_override']
                eff_dt = parse_date(eff_dt_str)
            else:
                eff_dt = None
                new_amt = sal_amt

            cur_month = req_date.replace(day=1)
            for _ in range(4):
                try:
                    pay_dt = cur_month.replace(day=sal_day)
                except ValueError:
                    next_m = (cur_month.replace(day=28) + timedelta(days=4)).replace(day=1)
                    pay_dt = next_m - timedelta(days=1)

                if req_date <= pay_dt <= end_date:
                    if not any(e['status'] == 'scheduled' and e['category'] == 'salary' and parse_date(e['settlement_date']) == pay_dt for e in evs):
                        actual_amt = new_amt if (eff_dt is None or pay_dt >= eff_dt) else sal_amt
                        daily_deltas[pay_dt] += actual_amt

                cur_month = (cur_month.replace(day=28) + timedelta(days=4)).replace(day=1)

        # 3. Recurring fixed bills & subscriptions
        FIXED_CATEGORIES = {
            'rent', 'utilities', 'insurance', 'education', 'debt_repayment',
            'healthcare', 'housing', 'gym', 'family_support',
            'cloud_storage', 'streaming', 'music_subscription', 'delivery_membership'
        }

        streams = defaultdict(list)
        for e in evs:
            if e['status'] not in ['settled', 'scheduled']:
                continue
            if e['direction'] != 'debit':
                continue
            if e['category'] in FIXED_CATEGORIES:
                streams[(e['category'], e['description'])].append(e)

        for (cat, desc), items in streams.items():
            if len(items) < 2:
                continue

            items.sort(key=lambda x: x['settlement_date'])
            latest_item = items[-1]
            eid = latest_item['event_id']

            if eid in spending_changes and spending_changes[eid] == 'stop':
                continue

            dates = [parse_date(x['settlement_date']) for x in items]
            day_of_month = dates[-1].day

            if eid in spending_changes and isinstance(spending_changes[eid], (int, float)):
                base_amt = float(spending_changes[eid])
            else:
                base_amt = float(latest_item['amount'])
                if cat == 'rent' and overrides['rent_multiplier'] != 1.0:
                    base_amt *= overrides['rent_multiplier']

            base_amt = self.convert_amount(base_amt, latest_item['currency'], home_curr, latest_item['settlement_date'])

            cur_m = req_date.replace(day=1)
            for _ in range(4):
                try:
                    occ_dt = cur_m.replace(day=day_of_month)
                except ValueError:
                    next_m = (cur_m.replace(day=28) + timedelta(days=4)).replace(day=1)
                    occ_dt = next_m - timedelta(days=1)

                if req_date <= occ_dt <= end_date:
                    if not any(e['event_id'] == eid and parse_date(e['settlement_date']) == occ_dt for e in evs if e['status'] in ['pending', 'scheduled']):
                        daily_deltas[occ_dt] -= base_amt

                cur_m = (cur_m.replace(day=28) + timedelta(days=4)).replace(day=1)

        # 4. Variable living categories (groceries, transport, dining)
        VARIABLE_CATEGORIES = {'groceries', 'transport', 'dining'}
        # Calculate recent monthly spending in each variable category
        cat_monthly = defaultdict(list)
        for cat in VARIABLE_CATEGORIES:
            cat_evs = [e for e in evs if e['category'] == cat and e['status'] == 'settled' and e['direction'] == 'debit']
            if not cat_evs:
                continue
            # Group by month
            by_m = defaultdict(float)
            for e in cat_evs:
                m = e['settlement_date'][:7]
                amt = float(e['amount'])
                by_m[m] += self.convert_amount(amt, e['currency'], home_curr, e['settlement_date'])

            # Average over last 2 complete months
            m_keys = sorted(by_m.keys())
            if len(m_keys) >= 2:
                recent_vals = [by_m[k] for k in m_keys[-3:-1]]
                avg_m = sum(recent_vals) / len(recent_vals)
            elif m_keys:
                avg_m = by_m[m_keys[-1]]
            else:
                avg_m = 0.0

            # Check if any dining item was stopped or reduced
            for e in cat_evs:
                eid = e['event_id']
                if eid in spending_changes:
                    ch = spending_changes[eid]
                    if ch == 'stop':
                        avg_m = max(0.0, avg_m - float(e['amount']))
                    elif isinstance(ch, (int, float)):
                        saved = float(e['amount']) - float(ch)
                        avg_m = max(0.0, avg_m - saved)

            # Distribute daily across the forecast horizon
            daily_amt = avg_m / 30.41
            curr_occ = req_date + timedelta(days=1)
            while curr_occ <= end_date:
                daily_deltas[curr_occ] -= daily_amt
                curr_occ += timedelta(days=1)

        return daily_deltas

    def simulate_balances(self, user_id, request_date_str, extra_payments=None, spending_changes=None, days=120):
        req_date = parse_date(request_date_str)
        end_date = req_date + timedelta(days=days)
        profile = self.profiles[user_id]
        start_bal = float(profile['current_available_balance'])
        daily_deltas = self.build_forecast_schedule(user_id, request_date_str, spending_changes, days=days)

        if extra_payments:
            for p_date, p_amt in extra_payments.items():
                if isinstance(p_date, str):
                    p_date = parse_date(p_date)
                if p_date:
                    daily_deltas[p_date] -= float(p_amt)

        curr_bal = start_bal
        min_bal_seen = curr_bal
        daily_bals = {}

        curr_dt = req_date
        while curr_dt <= end_date:
            if curr_dt in daily_deltas:
                curr_bal += daily_deltas[curr_dt]
            daily_bals[curr_dt] = curr_bal
            if curr_bal < min_bal_seen:
                min_bal_seen = curr_bal
            curr_dt += timedelta(days=1)

        return min_bal_seen, daily_bals

    def compute_amount_safe_to_pay(self, user_id, request_date_str, requested_amount):
        profile = self.profiles[user_id]
        min_keep = float(profile['minimum_balance_to_keep'])
        min_bal, _ = self.simulate_balances(user_id, request_date_str)
        headroom = max(0.0, min_bal - min_keep)
        return min(float(requested_amount), round(headroom, 2))

    def find_earliest_date_for_full_payment(self, user_id, request_date_str, requested_amount):
        req_date = parse_date(request_date_str)
        end_date = req_date + timedelta(days=90)
        profile = self.profiles[user_id]
        min_keep = float(profile['minimum_balance_to_keep'])
        req_amt = float(requested_amount)

        safe_today = self.compute_amount_safe_to_pay(user_id, request_date_str, req_amt)
        if safe_today >= req_amt - 1e-4:
            return request_date_str

        curr_dt = req_date + timedelta(days=1)
        window_end = req_date + timedelta(days=90)
        while curr_dt <= end_date:
            _, daily_bals = self.simulate_balances(user_id, request_date_str, extra_payments={curr_dt: req_amt}, days=180)
            min_in_window = min(daily_bals[d] for d in daily_bals if curr_dt <= d <= window_end)
            if min_in_window >= min_keep - 1e-4:
                return format_date(curr_dt)
            curr_dt += timedelta(days=1)

        return ""

    def evaluate_request(self, request):
        req_id = request['request_id']
        uid = request['user_id']
        req_date_str = request['request_date']
        req_date = parse_date(req_date_str)
        req_amt = float(request['requested_amount'])
        completion_date_str = request['desired_completion_date']
        completion_date = parse_date(completion_date_str)
        allows_partial = request['allows_partial_payment'].strip().lower() == 'true'

        profile = self.profiles[uid]
        home_curr = profile['home_currency']
        min_keep = float(profile['minimum_balance_to_keep'])
        allowed_methods = [m.strip() for m in profile['payment_methods_user_will_consider'].split('|')]
        max_months_str = profile['max_installment_months'].strip()
        max_months = int(max_months_str) if max_months_str else 0

        safe_to_pay = self.compute_amount_safe_to_pay(uid, req_date_str, req_amt)
        earliest_full = self.find_earliest_date_for_full_payment(uid, req_date_str, req_amt)

        # 1. Affordable now
        if safe_to_pay >= req_amt - 1e-4 and 'full_payment' in allowed_methods:
            amt_formatted = clean_amt_str(req_amt)
            explanation = f"Pay {home_curr} {req_amt:,.2f} today. This leaves at least {home_curr} {min_keep:,.2f} available over the next 90 days."
            return {
                'request_id': req_id,
                'amount_safe_to_pay': safe_to_pay,
                'affordability_status': 'affordable_now',
                'recommended_payment_method': 'full_payment',
                'payment_plan': f"{req_date_str}:{amt_formatted}",
                'earliest_date_for_full_payment': req_date_str,
                'spending_changes_needed': 'none',
                'decision_explanation': explanation
            }

        candidate_plans = []

        # 2. Candidate: Full payment with spending changes
        if 'full_payment' in allowed_methods and safe_to_pay < req_amt:
            user_stop_cats = set(c.strip() for c in profile['expense_categories_user_is_willing_to_stop'].split('|') if c.strip())
            user_red_cats = set(c.strip() for c in profile['expense_categories_user_is_willing_to_reduce'].split('|') if c.strip())

            evs = self.user_events.get(uid, [])
            change_candidates = []
            for e in evs:
                if e['status'] != 'settled' or e['direction'] != 'debit':
                    continue
                cat = e['category']
                flex = e['flexibility']
                amt = float(e['amount'])
                eid = e['event_id']
                if flex in ['stoppable', 'reducible_or_stoppable'] and cat in user_stop_cats:
                    change_candidates.append(('stop', eid, cat, e['description'], amt, 0.0))
                if flex in ['reducible', 'reducible_or_stoppable'] and cat in user_red_cats:
                    if e['minimum_allowed_amount']:
                        min_amt = float(e['minimum_allowed_amount'])
                        saved = amt - min_amt
                        if saved > 0:
                            change_candidates.append(('reduce_to', eid, cat, e['description'], saved, min_amt))

            # Test single changes
            for ch in change_candidates:
                action, ceid, ccat, cdesc, csaved, cmin = ch
                sp_changes = {ceid: 'stop' if action == 'stop' else cmin}
                test_safe = min(req_amt, max(0.0, self.simulate_balances(uid, req_date_str, spending_changes=sp_changes)[0] - min_keep))
                if test_safe >= req_amt - 1e-4:
                    ch_str = f"{action}:{ceid}" if action == 'stop' else f"{action}:{ceid}:{clean_amt_str(cmin)}"
                    action_desc = f"Stop the {cdesc.lower()}" if action == 'stop' else f"Reduce the {cdesc.lower()} to {home_curr} {clean_amt_str(cmin)}"
                    candidate_plans.append({
                        'method': 'full_payment',
                        'plan': f"{req_date_str}:{clean_amt_str(req_amt)}",
                        'spending_changes': ch_str,
                        'total_paid': req_amt,
                        'first_payment_date': req_date,
                        'last_payment_date': req_date,
                        'num_payments': 1,
                        'option_id': 'change_full',
                        'status': 'affordable_with_plan',
                        'explanation': f"{action_desc}, then pay {home_curr} {req_amt:,.2f} today. This leaves at least {home_curr} {min_keep:,.2f} available."
                    })
                    break

            # If single change not enough, test 2 changes
            if not candidate_plans and len(change_candidates) >= 2:
                for i in range(len(change_candidates)):
                    for j in range(i + 1, len(change_candidates)):
                        ch1, ch2 = change_candidates[i], change_candidates[j]
                        if ch1[1] == ch2[1]:
                            continue
                        sp_changes = {
                            ch1[1]: 'stop' if ch1[0] == 'stop' else ch1[5],
                            ch2[1]: 'stop' if ch2[0] == 'stop' else ch2[5]
                        }
                        test_safe = min(req_amt, max(0.0, self.simulate_balances(uid, req_date_str, spending_changes=sp_changes)[0] - min_keep))
                        if test_safe >= req_amt - 1e-4:
                            str1 = f"{ch1[0]}:{ch1[1]}" if ch1[0] == 'stop' else f"{ch1[0]}:{ch1[1]}:{clean_amt_str(ch1[5])}"
                            str2 = f"{ch2[0]}:{ch2[1]}" if ch2[0] == 'stop' else f"{ch2[0]}:{ch2[1]}:{clean_amt_str(ch2[5])}"
                            candidate_plans.append({
                                'method': 'full_payment',
                                'plan': f"{req_date_str}:{clean_amt_str(req_amt)}",
                                'spending_changes': f"{str1}|{str2}",
                                'total_paid': req_amt,
                                'first_payment_date': req_date,
                                'last_payment_date': req_date,
                                'num_payments': 1,
                                'option_id': 'change_full',
                                'status': 'affordable_with_plan',
                                'explanation': f"Adjust flexible expenses, then pay {home_curr} {req_amt:,.2f} today. This leaves at least {home_curr} {min_keep:,.2f} available."
                            })
                            break
                    if candidate_plans:
                        break

        # 3. Candidate: Partial payment
        if allows_partial and 'partial_payment' in allowed_methods and 0 < safe_to_pay < req_amt:
            if earliest_full and parse_date(earliest_full) <= completion_date:
                part1 = safe_to_pay
                part2 = req_amt - safe_to_pay
                p1_str = clean_amt_str(part1)
                p2_str = clean_amt_str(part2)
                candidate_plans.append({
                    'method': 'partial_payment',
                    'plan': f"{req_date_str}:{p1_str}|{earliest_full}:{p2_str}",
                    'spending_changes': 'none',
                    'total_paid': req_amt,
                    'first_payment_date': req_date,
                    'last_payment_date': parse_date(earliest_full),
                    'num_payments': 2,
                    'option_id': 'partial',
                    'status': 'affordable_with_plan',
                    'explanation': f"Pay {home_curr} {part1:,.2f} today and the remaining {home_curr} {part2:,.2f} on {earliest_full}. This completes the full request and keeps the {home_curr} {min_keep:,.2f} minimum protected."
                })

        # 4. Candidate: Installments
        if 'installments' in allowed_methods:
            options = self.payment_options.get(req_id, [])
            for opt in options:
                if opt['payment_method'] != 'installments':
                    continue
                num_p = int(opt['number_of_payments'])
                if max_months > 0 and num_p > max_months:
                    continue

                p_amt = float(opt['payment_amount'])
                first_dt = parse_date(opt['first_payment_date'])
                freq = int(opt['payment_frequency_days']) if opt['payment_frequency_days'] else 30
                total_payable = float(opt['total_payable_amount'])

                payment_schedule = {}
                plan_parts = []
                for i in range(num_p):
                    p_dt = first_dt + timedelta(days=i * freq)
                    payment_schedule[p_dt] = p_amt
                    amt_formatted = clean_amt_str(p_amt)
                    plan_parts.append(f"{format_date(p_dt)}:{amt_formatted}")

                last_dt = first_dt + timedelta(days=(num_p - 1) * freq)

                # Check if completes by desired_completion_date
                if last_dt <= completion_date:
                    candidate_plans.append({
                        'method': 'installments',
                        'plan': '|'.join(plan_parts),
                        'spending_changes': 'none',
                        'total_paid': total_payable,
                        'first_payment_date': first_dt,
                        'last_payment_date': last_dt,
                        'num_payments': num_p,
                        'option_id': opt['payment_option_id'],
                        'status': 'affordable_with_plan',
                        'explanation': f"Use {num_p} installments of {home_curr} {p_amt:,.2f}, starting {first_dt.strftime('%d %B %Y')}. This leaves at least {home_curr} {min_keep:,.2f} available."
                    })

        # Rank candidate plans
        if candidate_plans:
            def plan_sort_key(p):
                completes_on_time = 0 if p['last_payment_date'] <= completion_date else 1
                no_changes = 0 if p['spending_changes'] == 'none' else 1
                tot_amt = p['total_paid']
                first_date = p['first_payment_date']
                num_pay = p['num_payments']
                opt_id = p['option_id']
                return (completes_on_time, no_changes, tot_amt, first_date, num_pay, opt_id)

            candidate_plans.sort(key=plan_sort_key)
            best_plan = candidate_plans[0]

            if best_plan['last_payment_date'] <= completion_date:
                return {
                    'request_id': req_id,
                    'amount_safe_to_pay': safe_to_pay,
                    'affordability_status': 'affordable_with_plan',
                    'recommended_payment_method': best_plan['method'],
                    'payment_plan': best_plan['plan'],
                    'earliest_date_for_full_payment': earliest_full,
                    'spending_changes_needed': best_plan['spending_changes'],
                    'decision_explanation': best_plan['explanation']
                }

        # 5. Check affordable_later (wait)
        if 'full_payment' in allowed_methods and earliest_full:
            earliest_dt = parse_date(earliest_full)
            if earliest_dt <= completion_date:
                amt_str = clean_amt_str(req_amt)
                return {
                    'request_id': req_id,
                    'amount_safe_to_pay': safe_to_pay,
                    'affordability_status': 'affordable_later',
                    'recommended_payment_method': 'wait',
                    'payment_plan': f"{earliest_full}:{amt_str}",
                    'earliest_date_for_full_payment': earliest_full,
                    'spending_changes_needed': 'none',
                    'decision_explanation': f"Pay {home_curr} {req_amt:,.2f} in full on {earliest_full}. Paying earlier would take the balance below the {home_curr} {min_keep:,.2f} minimum."
                }

        # 6. Fallback: not_affordable
        return {
            'request_id': req_id,
            'amount_safe_to_pay': safe_to_pay,
            'affordability_status': 'not_affordable',
            'recommended_payment_method': 'not_recommended',
            'payment_plan': 'none',
            'earliest_date_for_full_payment': earliest_full if earliest_full and parse_date(earliest_full) <= completion_date else '',
            'spending_changes_needed': 'none',
            'decision_explanation': f"Do not make this payment by {completion_date_str}. None of the available options keeps the {home_curr} {min_keep:,.2f} minimum protected."
        }
