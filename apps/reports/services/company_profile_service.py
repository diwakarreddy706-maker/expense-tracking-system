from apps.reports.models import CompanyProfile


class CompanyProfileService:
    """
    Provides authoritative company / business profile data for reports and invoices.
    """

    @classmethod
    def get_profile(cls) -> CompanyProfile:
        """Retrieves active company profile or creates default."""
        profile = CompanyProfile.objects.filter(is_active=True).first()
        if not profile:
            profile = CompanyProfile.objects.create(
                business_name='Sri Basaveshwara Harvesting & Co',
                legal_name='Sri Basaveshwara Agricultural Contractor Services',
                phone='+91 98765 43210',
                email='contact@basaveshwara-harvesting.com',
                village='Harapanahalli Road',
                taluk='Harapanahalli',
                district='Vijayanagara',
                state='Karnataka',
                pin_code='583131',
                authorized_signatory_name='Managing Partner',
                authorized_signatory_designation='Authorized Signatory',
            )
        return profile
