from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from apps.dashboard.services.analytics_service import DashboardAnalyticsService


@login_required
def dashboard_index(request):
    """
    Renders the final executive dashboard template with authoritative KPIs.
    Protected by server-side authentication and role decorators.
    """
    kpis = DashboardAnalyticsService.get_executive_dashboard_kpis(user=request.user)

    context = {
        'title': 'Executive Business Dashboard',
        'kpis': kpis,
        'user_role': request.user.profile.role if hasattr(request.user, 'profile') else 'EMPLOYEE',
    }
    return render(request, 'dashboard/index.html', context)


@login_required
def dashboard_summary_api(request):
    """
    Authoritative JSON API endpoint returning all dashboard KPIs.
    """
    kpis = DashboardAnalyticsService.get_executive_dashboard_kpis(user=request.user)

    # Convert Decimals to string for JSON serialization
    def serialize_decimal_dict(d):
        res = {}
        for k, v in d.items():
            if hasattr(v, 'quantize') or isinstance(v, (int, float)):
                res[k] = str(v)
            elif isinstance(v, dict):
                res[k] = serialize_decimal_dict(v)
            elif isinstance(v, list):
                res[k] = [serialize_decimal_dict(item) if isinstance(item, dict) else str(item) for item in v]
            elif hasattr(v, 'isoformat'):
                res[k] = v.isoformat()
            elif hasattr(v, '__str__'):
                res[k] = str(v)
            else:
                res[k] = v
        return res

    data = {
        'status': 'foundation_ready',
        'today': str(kpis['today']),
        'opening_balance': str(kpis['opening_balance']),
        'money_received_today': str(kpis['money_received_today']),
        'money_spent_today': str(kpis['money_spent_today']),
        'expected_closing_today': str(kpis['expected_closing_today']),
        'actual_closing_today': str(kpis['actual_closing_today']) if kpis['actual_closing_today'] is not None else None,
        'closing_difference': str(kpis['closing_difference']),
        'closing_status': kpis['closing_status'],
        'is_day_closed': kpis['is_day_closed'],
        'receivables_to_receive': str(kpis['receivables_to_receive']),
        'payables_to_pay': str(kpis['payables_to_pay']),
        'employee_wages_due': str(kpis['employee_wages_due']),
        'operational_costs': {
            'fuel': str(kpis['fuel_cost_month']),
            'maintenance': str(kpis['maintenance_cost_month']),
            'wages': str(kpis['emp_payouts_month']),
            'other': str(kpis['other_expenses_month']),
            'total': str(kpis['total_expenses_month']),
        },
        'budget': {
            'budgeted': str(kpis['budget_summary']['total_budgeted']),
            'spent': str(kpis['budget_summary']['total_spent']),
            'remaining': str(kpis['budget_summary']['total_remaining']),
            'utilization_pct': str(kpis['budget_summary']['overall_utilization']),
            'status': kpis['budget_summary']['status'],
        },
        'machine_costs': [
            {
                'machine_code': m['machine_code'],
                'name': m['name'],
                'total_cost': str(m['total_cost']),
                'fuel_cost': str(m['fuel_cost']),
                'maintenance_cost': str(m['maintenance_cost']),
                'current_meter': str(m['current_meter']),
                'cost_per_unit': str(m['cost_per_unit']),
            }
            for m in kpis['machine_costs']
        ]
    }
    return JsonResponse(data)
