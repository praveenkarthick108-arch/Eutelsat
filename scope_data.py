# Phase 1 — Foundation Capability (light blue items from CxP Capability Set)
# Systems: GEO Community Cloud (Portal), GCRM Salesforce (Contracts), Zuora (CPQ/Billing),
#          GEO Salesforce (Orders/Celfocus OM), Oracle BRM (O-BRM), SAP S4HANA,
#          Axiros (Provisioning/Device Mgmt), MuleSoft LEO (Integration), ServiceNow (ITSM)

SCOPE = {
    "Customer Portal": {
        "system": "GEO Community Cloud",
        "phase": 1,
        "features": [
            "Portal - Customer 360 degree view",
            "LEO Order journey for packages & Sub Pools",
            "Portal - DP-Sub-DB user access management",
            "Streamlined Order journey - infra",
            "Portal - customer inventory management",
            "Portal - customer hierarchy view",
            "Expose UT, Service & Performance view",
            "Capped Data Allowance (Hard)",
        ],
    },
    "Contracts / CIM": {
        "system": "GCRM Salesforce",
        "phase": 1,
        "features": [
            "Standard LEO product structure setup",
            "Standard contract model setup",
            "Standard DP specific options at contract level",
            "Standard contract rules execution model",
            "Standard Contract management rules",
            "Customer Account Setup (global/local)",
        ],
    },
    "CPQ / EPC": {
        "system": "Zuora",
        "phase": 1,
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
        "system": "GEO Salesforce / Celfocus OM",
        "phase": 1,
        "features": [
            "LEO Partner Service setup for ordering",
            "Streamlined Order journey - general",
            "Streamlined Order journey - activation",
            "Streamlined Order journey - changes (technical)",
            "Streamlined Order journey - changes (commercial)",
            "Streamlined Order journey - termination",
            "Streamlined Order journey - renewals",
            "OM for Undisclosed mode",
        ],
    },
    "Provisioning / Activation": {
        "system": "Axiros / Celfocus OM",
        "phase": 1,
        "features": [
            "LEO device provisioning via Axiros",
            "Service activation end-to-end flow",
            "Device configuration & commissioning",
            "Provisioning status tracking & callbacks",
            "Error recovery & re-provisioning flows",
            "Axiros-to-OM status synchronisation",
            "DP terminal onboarding & activation",
            "Deactivation & suspension handling",
        ],
    },
    "Billing / Charging": {
        "system": "Zuora / O-BRM",
        "phase": 1,
        "features": [
            "Core Billing model setup",
            "Billing - Re-Rating model setup",
            "Billing - Legal / Local Entity setup",
            "Billing - Local currency setup",
            "Process payload received from Rating engine for Billing",
            "Bill Override procedures",
            "Billing - True-up & credits processing",
            "Capability to bill A-PNT device and service",
        ],
    },
    "Inv. & Accounting": {
        "system": "SAP S4HANA",
        "phase": 1,
        "features": [
            "Tax calculation and invoice generation",
            "Push invoice to the portal",
            "Expose APIs for Invoicing and Accounting details",
            "Customer Account Setup (global/local)",
            "Support A-PNT device & service",
        ],
    },
    "API / Integration": {
        "system": "MuleSoft LEO / Multiple",
        "phase": 1,
        "features": [
            "Catalogue Sync (Zuora > OBRM)",
            "Customer order Mgmt. (SF > Celfocus)",
            "Account federation (GCRM > full stack)",
            "Prod. Inventory federation (SF > full stack)",
            "Re/Rated CDR to Bill (OBRM > Zuora)",
            "Bill to invoice (Zuora > SAP)",
            "Contract sync (GCRM > SF)",
            "Customer 360 view (many > SF Community cloud)",
            "Customer Order Management APIs",
            "Customer Order Management APIs (Pools)",
            "Accounting & Invoicing (SAP > DP)",
            "Axiros provisioning callbacks (Axiros > Celfocus)",
            "ServiceNow incident & change integration",
        ],
    },
    "ServiceNow / ITSM": {
        "system": "ServiceNow",
        "phase": 1,
        "features": [
            "Incident management integration",
            "Change request workflow for releases",
            "Problem management linkage to defects",
            "ServiceNow-to-Jira defect sync",
            "Release readiness gates in ServiceNow",
            "SLA breach alerting & escalation",
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
        "Customer Account Setup (global/local)",
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
    "Provisioning / Activation": [
        "LEO device provisioning via Axiros",
        "Streamlined Order journey - activation",
        "Customer order Mgmt. (SF > Celfocus)",
        "Axiros provisioning callbacks (Axiros > Celfocus)",
        "DP terminal onboarding & activation",
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
        "Accounting & Invoicing (SAP > DP)",
    ],
    "API / Integration": [
        "Catalogue Sync (Zuora > OBRM)",
        "Contract sync (GCRM > SF)",
        "Account federation (GCRM > full stack)",
        "Bill to invoice (Zuora > SAP)",
        "Customer Order Management APIs",
    ],
    "ServiceNow / ITSM": [
        "ServiceNow incident & change integration",
        "Incident management integration",
        "Change request workflow for releases",
        "ServiceNow-to-Jira defect sync",
        "Release readiness gates in ServiceNow",
    ],
}

# Release structure (from Prodapt Lot B response)
RELEASES = {
    "R1": {
        "name": "R1 – Foundation Release",
        "focus": "New DP onboarding, core E2E journeys, integration/API testing, initial regression automation",
        "automation_target": "30–40% regression automated, core happy paths",
        "test_focus": [
            "Core E2E journey execution",
            "Integration & API testing",
            "Release readiness validation",
            "Happy path & critical negative scenarios",
        ],
    },
    "R2": {
        "name": "R2 – Migration Ramp Up",
        "focus": "Partial migration, data integrity, billing correctness across legacy and new stack",
        "automation_target": "65–75% regression automated, migration sanity & reconciliation",
        "test_focus": [
            "Migration data validation",
            "Integration & API revalidation",
            "Billing correctness across legacy/new stack",
            "Progression automation on migrated DPs",
        ],
    },
    "R3": {
        "name": "R3 – Full Migration & Stabilization",
        "focus": "Full migration, performance validation, go-live readiness",
        "automation_target": ">90% regression automation, only complex edge cases manual",
        "test_focus": [
            "Full E2E regression (automated)",
            "Performance validation (API level)",
            "Go-live readiness & sign-off",
            "Cutover & post-migration validation",
        ],
    },
}

# KPI targets from Eutelsat CxP programme
KPI_TARGETS = {
    "ordering_automation": ">=90% automation for key business service processes",
    "catalogue_reduction": "<80% reduction in time to create/modify catalogue items",
    "billing_accuracy": ">=90% billing accuracy rate across all products",
    "api_response_time": "<2 seconds API response time for Portal",
    "data_migration_accuracy": ">=98% accuracy in migrating DP data",
    "defect_leakage": "<2% defect leakage rate",
    "defect_detection_efficiency": ">96% defect detection efficiency",
    "regression_automation": ">90% regression automation coverage (R3 target)",
    "defect_aging": "<5 days average defect aging",
}

MATCH_PCT = [96, 89, 83, 77, 71]
