SCOPE = {
    "Customer Portal": {
        "system": "GEO Community Cloud",
        "features": [
            "Portal - Customer 360 degree view",
            "LEO Order journey for packages & Sub Pools",
            "Portal - DP-Sub-DB user access management",
            "Streamlined Order journey - infra",
            "Portal - customer inventory management",
        ],
    },
    "Contracts / CIM": {
        "system": "GCRM Salesforce",
        "features": [
            "Standard LEO product structure setup",
            "Standard contract model setup",
            "Standard DP specific options at contract level",
            "Standard contract rules execution model",
            "Standard Contract management rules",
        ],
    },
    "CPQ / EPC": {
        "system": "Zuora",
        "features": [
            "Baseline Product Catalogue model - core",
            "Baseline Product Pricing structure setup",
            "Network Slice model setup",
            "Baseline Product Catalogue model - options",
            "Support DP specific catalogue config",
            "Baseline Product Management / Visibility rules",
        ],
    },
    "Order Management": {
        "system": "GEO Salesforce",
        "features": [
            "LEO Partner Service setup for ordering",
            "Streamlined Order journey - general",
            "Streamlined Order journey - activation",
            "Streamlined Order journey - changes (technical)",
            "Streamlined Order journey - changes (commercial)",
            "Streamlined Order journey - termination",
        ],
    },
    "Billing / Charging": {
        "system": "Zuora / O-BRM",
        "features": [
            "Core Billing model setup",
            "Billing - Re-Rating model setup",
            "Billing - Legal / Local Entity setup",
            "Billing - Local currency setup",
            "Process payload received from Rating engine for Billing",
        ],
    },
    "Inv. & Accounting": {
        "system": "SAP",
        "features": [
            "Tax calculation and invoice generation",
            "Push invoice to the portal",
            "Expose APIs for Invoicing and Accounting details",
        ],
    },
    "API / Integration": {
        "system": "Multiple inc. logic",
        "features": [
            "Catalogue Sync (Zuora > OBRM)",
            "Customer order Mgmt. (SF > Celfocus)",
            "Account federation (GCRM > full stack)",
            "Prod. Inventory federation (SF > full stack)",
            "Re/Rated CDR to Bill (OBRM > Zuora)",
            "Bill to invoice (Zuora > SAP)",
            "Contract sync (GCRM > SF)",
            "Customer 360 view (many > SF Community cloud)",
        ],
    },
}

RELATED = {
    "Customer Portal": [
        "LEO Order journey for packages & Sub Pools",
        "Catalogue Sync (Zuora > OBRM)",
        "Customer 360 view (many > SF Community cloud)",
        "Standard LEO product structure setup",
        "Streamlined Order journey - general",
    ],
    "Contracts / CIM": [
        "Standard LEO product structure setup",
        "Baseline Product Catalogue model - core",
        "Contract sync (GCRM > SF)",
        "Account federation (GCRM > full stack)",
        "Standard contract model setup",
    ],
    "CPQ / EPC": [
        "Baseline Product Pricing structure setup",
        "Core Billing model setup",
        "Catalogue Sync (Zuora > OBRM)",
        "Network Slice model setup",
        "Baseline Product Catalogue model - options",
    ],
    "Order Management": [
        "Streamlined Order journey - general",
        "LEO Partner Service setup for ordering",
        "Customer order Mgmt. (SF > Celfocus)",
        "Core Billing model setup",
        "Streamlined Order journey - activation",
    ],
    "Billing / Charging": [
        "Core Billing model setup",
        "Re/Rated CDR to Bill (OBRM > Zuora)",
        "Bill to invoice (Zuora > SAP)",
        "Tax calculation and invoice generation",
        "Billing - Re-Rating model setup",
    ],
    "Inv. & Accounting": [
        "Tax calculation and invoice generation",
        "Bill to invoice (Zuora > SAP)",
        "Push invoice to the portal",
        "Expose APIs for Invoicing and Accounting details",
        "Core Billing model setup",
    ],
    "API / Integration": [
        "Catalogue Sync (Zuora > OBRM)",
        "Contract sync (GCRM > SF)",
        "Account federation (GCRM > full stack)",
        "Bill to invoice (Zuora > SAP)",
        "Customer order Mgmt. (SF > Celfocus)",
    ],
}

MATCH_PCT = [96, 89, 83, 77, 71]
