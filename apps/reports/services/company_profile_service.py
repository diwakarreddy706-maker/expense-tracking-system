from apps.reports.models import CompanyProfile


class CompanyProfileService:
    """
    Provides authoritative company / business profile data for reports and invoices.
    """
    _cached_profile = None

    @classmethod
    def get_profile(cls, force_refresh: bool = False) -> CompanyProfile:
        """Retrieves active company profile or creates default."""
        if cls._cached_profile is not None and not force_refresh:
            return cls._cached_profile

        try:
            profile = CompanyProfile.objects.filter(is_active=True).first()
            if not profile:
                profile = CompanyProfile.objects.create(
                    business_name='Sri Basaveshwara Harvesting & Co',
                    legal_name='Sri Basaveshwara Agricultural Contractor Services',
                    tagline='Agricultural Harvesting & Heavy Equipment Fleet Hub',
                    phone='+91 98801 99000',
                    email='contact@basaveshwara-harvesting.com',
                    village='Harapanahalli Road',
                    taluk='Harapanahalli',
                    district='Vijayanagara',
                    state='Karnataka',
                    pin_code='583131',
                    authorized_signatory_name='Doddana Gowda',
                    authorized_signatory_designation='Managing Partner',
                )
            cls._cached_profile = profile
            return profile
        except Exception:
            # Fallback in-memory instance if database is initializing
            return CompanyProfile(
                business_name='Sri Basaveshwara Harvesting & Co',
                tagline='Agricultural Harvesting & Heavy Equipment Fleet Hub',
                phone='+91 98801 99000',
                village='Harapanahalli Road',
                taluk='Harapanahalli',
                district='Vijayanagara',
                state='Karnataka',
                pin_code='583131'
            )

    @classmethod
    def invalidate_cache(cls):
        """Clears the cached profile when updated."""
        cls._cached_profile = None

