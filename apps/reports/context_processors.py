from apps.reports.services.company_profile_service import CompanyProfileService


def company_context(request):
    """
    Context processor injecting active company branding into all templates.
    """
    return {
        'company_profile': CompanyProfileService.get_profile()
    }
