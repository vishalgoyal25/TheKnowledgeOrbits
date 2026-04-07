"""
backend/engines/book_content/management/commands/seed_syllabus.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase F — UPSC Syllabus Seed Command

Seeds the complete UPSC CSE syllabus hierarchy into the knowledge_* tables.

Hierarchy:
  Program (UPSC CSE)
    └── Subject        (e.g. "Indian Polity & Constitution")
          └── Module   (e.g. "Fundamental Rights & Duties")
                └── Topic        (e.g. "Right to Equality")
                      └── Subtopic     (e.g. "Article 14 — Equality Before Law")
                            └── Sub-subtopic (e.g. "Reasonable Classification Doctrine")

Usage:
  # Seed everything (safe to re-run — fully idempotent via get_or_create)
  python manage.py seed_syllabus

  # Seed only one subject (for testing / incremental addition)
  python manage.py seed_syllabus --subject "Indian Polity & Constitution"

  # Dry-run: print what would be created without touching the DB
  python manage.py seed_syllabus --dry-run

Design rules:
  - get_or_create at EVERY level → 100% idempotent, re-run anytime
  - order_index preserved from SYLLABUS dict ordering → stable sort
  - node_type set correctly at every level for KnowledgeGraph rendering
  - is_active=True on all nodes so they appear in hamburger/navbar/graph
  - NO deletion — only addition. Removing a subject requires manual DB action.
  - Prints a summary after each subject: modules, topics, subtopics created
  - Works on local PostgreSQL and Supabase (same schema)

Adding new subjects:
  Just add a new key to SYLLABUS dict below and re-run the command.
  Existing records are untouched (get_or_create). Zero risk.

Structure of SYLLABUS dict:
  {
    "Subject Name": {
      "Module Name": {
        "Topic Name": {
          "Subtopic Name": [
            "Sub-subtopic A",
            "Sub-subtopic B",
            ...
          ],
          ...
        },
        ...
      },
      ...
    },
    ...
  }

  If a topic has NO subtopics → use an empty dict {}
  If a subtopic has NO sub-subtopics → use an empty list []
"""

import structlog
from django.core.management.base import BaseCommand
from django.db import transaction

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# SYLLABUS DATA
# Subjects are added one by one as user provides and verifies each.
# Format: { Subject: { Module: { Topic: { Subtopic: [Sub-subtopics] } } } }
# ═══════════════════════════════════════════════════════════════════════════════

SYLLABUS: dict = {
    # ═══════════════════════════════════════════════════════════════════════════
    # GS PAPER I
    # ═══════════════════════════════════════════════════════════════════════════
    "Indian Heritage & Culture": {
        "Indian Philosophy": {
            "Buddhism": {
                "Historical Background and Spread of Buddhism": [],
                "Core Teachings: Four Noble Truths and Eightfold Path": [],
                "Buddhist Councils and Major Sects": [],
                "Buddhist Art, Architecture and Literature": [],
                "Decline of Buddhism in India": [],
            },
            "Jainism": {
                "Origins and Teachings of Mahavira": [],
                "Core Principles: Ahimsa, Anekantavada, Syadvada": [],
                "Digambara and Shvetambara Sects": [],
                "Jain Art, Architecture and Literature": [],
                "Jainism's Contribution to Indian Culture": [],
            },
            "Hindu Philosophical Schools": {
                "Nyaya and Vaisheshika Schools": [],
                "Samkhya and Yoga Philosophy": [],
                "Purva Mimamsa and Vedanta": [],
                "Charvaka: Materialist Philosophy": [],
            },
            "Bhakti and Sufi Philosophy": {
                "Bhakti Movement: Philosophy and Spread": [],
                "Sufi Orders and Teachings": [],
                "Bhakti-Sufi Synthesis and Social Impact": [],
            },
            "Sikhism": {
                "Origins and Core Teachings of Sikhism": [],
                "Guru Tradition and Guru Granth Sahib": [],
                "Sikhism as a Social Reform Movement": [],
            },
        },
        "Indian Literature": {
            "Vedic Literature": {
                "Four Vedas: Rig, Sama, Yajur, Atharva": [],
                "Brahmanas, Aranyakas and Upanishads": [],
                "Significance and Themes of Vedic Literature": [],
            },
            "Epic and Classical Sanskrit Literature": {
                "Ramayana and Mahabharata: Themes and Significance": [],
                "Kalidasa and Classical Sanskrit Poetry": [],
                "Arthashastra, Manusmriti, Natyashastra": [],
            },
            "Buddhist and Jain Literature": {
                "Tripitaka and Pali Canon": [],
                "Jain Agamas and Sacred Literature": [],
                "Contribution to Regional Languages": [],
            },
            "Sangam Literature": {
                "Overview of Sangam Age Literature": [],
                "Major Works: Tolkappiyam, Purananuru": [],
                "Historical Significance of Sangam Literature": [],
            },
            "Bhakti and Sufi Literature": {
                "Saint-Poets: Kabir, Mirabai, Tukaram, Chaitanya": [],
                "Sufi Literature and Poetry in India": [],
                "Regional Language Development through Bhakti": [],
            },
            "Modern Indian Literature": {
                "Literature During Freedom Struggle": [],
                "Progressive Writers Movement": [],
                "Contemporary Indian Writing in English": [],
            },
        },
        "Indian Architecture": {
            "Cave Architecture": {
                "Ajanta and Ellora Caves": [],
                "Karla, Bhaja and Rock-cut Architecture": [],
                "Stylistic Features and Evolution": [],
            },
            "Schools of Art": {
                "Gandhara School of Art": [],
                "Mathura School of Art": [],
                "Amaravati School of Art": [],
            },
            "Temple Architecture": {
                "Nagara Style: North Indian Temples": [],
                "Dravida Style: South Indian Temples": [],
                "Vesara Style and Key Architectural Elements": [],
            },
            "Indo-Islamic Architecture": {
                "Delhi Sultanate Architecture": [],
                "Mughal Architecture: Features and Monuments": [],
                "Provincial and Regional Islamic Styles": [],
                "Syncretic Features of Indo-Islamic Art": [],
            },
            "Modern Art and Architecture": {
                "Indo-Gothic and Neo-Roman Architecture": [],
                "Miniature Painting Traditions": [],
                "Bengal School and Modern Indian Painting": [],
                "Mural and Wall Paintings": [],
            },
        },
        "Performing Arts": {
            "Indian Classical Dance": {
                "Bharatanatyam and Kathak": [],
                "Odissi, Kuchipudi and Manipuri": [],
                "Kathakali, Mohiniyattam and Sattriya": [],
            },
            "Indian Music": {
                "Hindustani Classical Music": [],
                "Carnatic Classical Music": [],
                "Folk Music Traditions of India": [],
            },
            "Indian Theatre and Puppetry": {
                "Classical Sanskrit Theatre": [],
                "Folk Theatre Traditions": [],
                "Traditional Puppetry Forms": [],
                "Indian Martial Arts: Kalaripayattu and Thang-ta": [],
            },
        },
        "Religious Movements": {
            "19th Century Socio-Religious Reform Movements": {
                "Brahmo Samaj and Raja Ram Mohan Roy": [],
                "Arya Samaj and Dayananda Saraswati": [],
                "Ramakrishna Mission and Swami Vivekananda": [],
                "Theosophical Society": [],
            },
            "Caste and Social Reform Movements": {
                "Jyotiba Phule and Satyashodhak Samaj": [],
                "Dr B R Ambedkar and Dalit Movement": [],
                "Self-Respect Movement and Periyar": [],
            },
        },
        "Other Cultural Aspects": {
            "Indian Languages and Scripts": {
                "Language Families in India": [],
                "Development of Indian Scripts": [],
                "Classical Language Status in India": [],
            },
            "Fairs, Festivals and Cultural Traditions": {
                "Major Religious Festivals of India": [],
                "Regional Folk Traditions and Crafts": [],
                "Cultural Institutions in India": [],
            },
            "Ancient Indian Science and Technology": {
                "Mathematics: Aryabhata and Brahmagupta": [],
                "Ancient Indian Astronomy and Medicine": [],
                "Metallurgy and Chemistry in Ancient India": [],
            },
        },
    },
    "Modern Indian History": {
        "India Under Colonial Rule": {
            "India in the Late 18th Century": {
                "Decline of the Mughal Empire": [],
                "Rise of Regional Powers and Successor States": [],
                "Socio-economic Conditions Before British Rule": [],
            },
            "European Advent and British Conquest": {
                "Portuguese, Dutch and French East India Companies": [],
                "Battle of Plassey and Buxar": [],
                "Subsidiary Alliance and Doctrine of Lapse": [],
            },
            "India Under the East India Company": {
                "Administrative and Economic Policies": [],
                "Economic Drain and De-Industrialisation": [],
                "Social and Cultural Impact of Company Rule": [],
            },
            "Revolt of 1857": {
                "Causes of the Revolt of 1857": [],
                "Course of the Revolt and Key Leaders": [],
                "Aftermath and Administrative Changes After 1858": [],
            },
        },
        "Freedom Struggle": {
            "Early Nationalist Phase: Moderates": {
                "Formation of Indian National Congress": [],
                "Moderate Methods: Petitions and Prayers": [],
                "Economic Critique of Colonial Rule": [],
            },
            "Extremist Phase": {
                "Bal Gangadhar Tilak and Rise of Extremism": [],
                "Partition of Bengal and Swadeshi Movement": [],
                "Revolutionary Nationalism": [],
            },
            "Gandhian Phase": {
                "Gandhi's Arrival and Champaran Satyagraha": [],
                "Non-Cooperation Movement": [],
                "Civil Disobedience Movement and Salt March": [],
                "Quit India Movement": [],
            },
            "Revolutionary Nationalism": {
                "Revolutionary Organisations and Leaders": [],
                "Bhagat Singh and HSRA": [],
                "Indian National Army and Subhas Chandra Bose": [],
            },
        },
        "Socio-Religious Reform Movements": {
            "19th and 20th Century Social Reform": {
                "Sati Abolition and Widow Remarriage Movement": [],
                "Women's Education and Organisations": [],
                "Role of Women in Freedom Struggle": [],
            },
            "Peasant and Tribal Movements": {
                "Indigo Revolt and Peasant Movements": [],
                "Tribal Uprisings: Santhal, Munda, Bhil": [],
                "Regional Movements and Princely States": [],
            },
        },
        "Post-Independence India": {
            "Partition and Integration of India": {
                "Partition of India and Its Consequences": [],
                "Integration of Princely States": [],
                "Sardar Patel's Role in Unification": [],
            },
            "Reorganisation of States": {
                "States Reorganisation Act 1956": [],
                "Linguistic States and Associated Controversy": [],
                "Northeast India and Tribal Policy": [],
            },
            "Early Decades of Independent India": {
                "Nehru Era: Democratic Socialism": [],
                "Indira Gandhi Period and Emergency": [],
                "Post-Emergency Political Developments": [],
            },
        },
    },
    "World History": {
        "Industrial and Political Revolutions": {
            "Industrial Revolution": {
                "Origins of Industrial Revolution in Britain": [],
                "Spread to Europe and America": [],
                "Social and Economic Impact of Industrialisation": [],
            },
            "American Revolution": {
                "Causes and Course of the American Revolution": [],
                "Constitutional Democracy and Its Global Impact": [],
            },
            "French Revolution": {
                "Causes and Phases of the French Revolution": [],
                "Napoleonic Era and Spread of Democratic Ideas": [],
            },
        },
        "Unification and Nationalism": {
            "Unification of Germany": {
                "Bismarck and German Unification": [],
                "Franco-Prussian War and Its Impact": [],
            },
            "Unification of Italy": {
                "Mazzini, Garibaldi and Cavour": [],
                "Role of Piedmont-Sardinia": [],
            },
            "Russian Revolution": {
                "Causes: Social and Economic Context": [],
                "1905 and 1917 Revolutions": [],
                "Rise of the Soviet State": [],
            },
        },
        "World Wars and Cold War": {
            "World War I": {
                "Causes and the Alliance System": [],
                "Course of the War and Key Battles": [],
                "Peace Treaties and Post-War World Order": [],
            },
            "World War II": {
                "Rise of Fascism and Nazism": [],
                "Course of WWII and Key Theatres": [],
                "Holocaust, Human Rights and Post-War Order": [],
            },
            "Cold War": {
                "Origins and Phases of the Cold War": [],
                "Non-Alignment Movement": [],
                "Disintegration of USSR and Its Aftermath": [],
            },
        },
        "Colonialism and Decolonisation": {
            "European Colonialism": {
                "Scramble for Africa": [],
                "Asian Colonisation and Its Impact": [],
                "Economic Exploitation Under Colonialism": [],
            },
            "Decolonisation Movements": {
                "Independence Movements in Asia": [],
                "African Nationalism and Independence": [],
                "Role of the UN in Decolonisation": [],
            },
        },
        "Political Philosophies": {
            "Capitalism and Liberalism": {
                "Origins and Development of Capitalism": [],
                "Neo-liberalism and Globalisation": [],
            },
            "Communism and Socialism": {
                "Marxist Theory: Foundations": [],
                "Soviet Model and Its Collapse": [],
                "Socialist Movements Around the World": [],
            },
            "Fascism and Nazism": {
                "Ideological Foundations of Fascism": [],
                "Rise of Nazism in Germany": [],
                "Lessons from Totalitarianism": [],
            },
        },
    },
    "Indian Society": {
        "Salient Features of Indian Society": {
            "Caste System in India": {
                "Origins and Structure of Caste System": [],
                "Dynamics of Caste in Modern India": [],
                "Caste and Electoral Politics": [],
                "Constitutional Provisions and Affirmative Action": [],
            },
            "Kinship, Marriage and Family": {
                "Kinship Systems in India": [],
                "Marriage Patterns and Types in India": [],
                "Changing Family Structure in India": [],
            },
            "Sanskritization and Social Mobility": {
                "M N Srinivas and the Concept of Sanskritization": [],
                "Westernisation and Modernisation in India": [],
                "Dominant Caste Theory": [],
            },
            "Tribal Society in India": {
                "Major Tribal Groups and Their Distribution": [],
                "Constitutional Safeguards for Tribes": [],
                "Tribal Development Issues and Conflicts": [],
            },
        },
        "Diversity and Unity": {
            "Religious Diversity in India": {
                "Major Religions and Their Distribution": [],
                "Religious Pluralism and Tolerance": [],
                "Communal Harmony Initiatives": [],
            },
            "Linguistic Diversity": {
                "Language Families and Distribution in India": [],
                "Language Policy and Constitutional Provisions": [],
                "Linguistic Conflicts and Solutions": [],
            },
            "Ethnic and Regional Diversity": {
                "Ethnic Groups and Their Identity": [],
                "Regional Identities and Their Expression": [],
                "Unity in Diversity: Integrating Forces": [],
            },
        },
        "Women and Gender": {
            "Women's Role in Indian Society": {
                "Historical Evolution of Women's Status": [],
                "Current Status: Education, Economy, Politics": [],
                "Women Organisations and Movements": [],
            },
            "Gender Issues and Challenges": {
                "Violence Against Women": [],
                "Patriarchy and Social Norms": [],
                "Gender Pay Gap and Economic Inequality": [],
            },
            "Government Initiatives for Women": {
                "Constitutional Provisions for Gender Equality": [],
                "Key Schemes and Acts for Women": [],
                "Women in Panchayati Raj Institutions": [],
            },
        },
        "Population and Poverty": {
            "Population Issues in India": {
                "Population Growth and Distribution": [],
                "Demographic Dividend and Its Challenges": [],
                "Population Policy and Family Planning": [],
                "Aging Population and Its Implications": [],
            },
            "Poverty in India": {
                "Types and Measurement of Poverty": [],
                "Causes and Consequences of Poverty": [],
                "Rural vs Urban Poverty": [],
                "Government Poverty Alleviation Programmes": [],
            },
        },
        "Urbanisation and Globalisation": {
            "Urbanisation in India": {
                "Trends, Patterns and Causes": [],
                "Urban Problems: Slums, Migration and Infrastructure": [],
                "Smart Cities Mission and Urban Planning": [],
                "Urbanisation and Feminisation of Agriculture": [],
            },
            "Effects of Globalisation on Indian Society": {
                "Economic Impacts of Globalisation": [],
                "Cultural Changes and Identity Crisis": [],
                "Impact on Women, Children and Elderly": [],
            },
        },
        "Communalism, Regionalism and Secularism": {
            "Communalism": {
                "Meaning, Types and Historical Roots": [],
                "Causes and Contemporary Manifestations": [],
                "Role of State and Media in Combating Communalism": [],
            },
            "Regionalism": {
                "Regional Movements in Post-Independence India": [],
                "Regionalism, Federalism and Nationalism": [],
                "Son-of-Soil Concept and Its Implications": [],
            },
            "Secularism in India": {
                "Indian vs Western Secularism": [],
                "Constitutional Provisions on Secularism": [],
                "Challenges to Indian Secularism": [],
            },
        },
        "Social Empowerment": {
            "SC, ST and OBC Empowerment": {
                "Constitutional Provisions for SC and ST": [],
                "Reservation Policy in India": [],
                "Recent Developments and Debates": [],
            },
            "Minority Rights and Protection": {
                "Constitutional Provisions for Minorities": [],
                "Minority Educational Institutions": [],
                "Issues and Challenges Facing Minorities": [],
            },
        },
    },
    "Indian & World Geography": {
        "Physical Geography of the World": {
            "Earth and Solar System": {
                "Solar System Basics and Earth's Formation": [],
                "Earth's Interior Structure": [],
                "Plate Tectonics and Continental Drift": [],
            },
            "Geomorphology": {
                "Rock Types: Igneous, Sedimentary, Metamorphic": [],
                "Internal Forces: Volcanism and Earthquakes": [],
                "External Forces: Erosion, Weathering, Deposition": [],
                "Landform Types and Their Formation": [],
            },
            "Climatology": {
                "Atmospheric Structure and Composition": [],
                "Pressure Belts and Wind Systems": [],
                "Monsoon Systems and Jet Streams": [],
                "World Climatic Regions": [],
            },
            "Oceanography": {
                "Ocean Currents and Their Effects on Climate": [],
                "Tides, Waves and El Nino": [],
                "Ocean Temperature, Salinity and Marine Resources": [],
            },
        },
        "Physical Geography of India": {
            "Location and Physiographic Divisions": {
                "Location, Extent and Boundaries of India": [],
                "Himalayan Region: Formation and Ranges": [],
                "Indo-Gangetic Plain and Peninsular Plateau": [],
                "Coastal Plains, Islands and Offshore Features": [],
            },
            "Indian Climate and Monsoon": {
                "Factors Affecting Indian Climate": [],
                "Monsoon Mechanism and Onset": [],
                "Seasons and Climatic Regions of India": [],
            },
            "Indian Rivers and Water Bodies": {
                "Himalayan River Systems: Ganga, Indus, Brahmaputra": [],
                "Peninsular River Systems": [],
                "Inter-basin Water Transfer Projects": [],
                "Inland Water Bodies and Lakes": [],
            },
            "Soils and Natural Vegetation of India": {
                "Soil Types and Their Distribution": [],
                "Natural Vegetation Zones of India": [],
                "Biodiversity Hotspots of India": [],
            },
        },
        "Human and Economic Geography": {
            "World Population and Migration": {
                "Global Population Distribution and Density": [],
                "International Migration Patterns": [],
                "Refugee Crisis and Global Response": [],
            },
            "Natural Resources and Their Distribution": {
                "Energy Resources: Conventional and Non-conventional": [],
                "Mineral Resources and Global Distribution": [],
                "Water Resources and Freshwater Crisis": [],
            },
            "Agriculture and Industry": {
                "Agro-Climatic Regions of the World": [],
                "Industrial Location Factors": [],
                "World Industrial Regions": [],
            },
        },
        "Indian Economic Geography": {
            "Indian Agriculture": {
                "Cropping Patterns and Agricultural Seasons": [],
                "Major Crops and Their Distribution in India": [],
                "Irrigation Systems in India": [],
            },
            "Indian Industries and SEZs": {
                "Major Industries and Their Location Factors": [],
                "Industrial Policy Evolution": [],
                "Special Economic Zones": [],
            },
            "Transport and Communication in India": {
                "Road and National Highway Network": [],
                "Railway Network and Modernisation": [],
                "Air, Water Transport and Communication": [],
            },
        },
        "Geophysical Phenomena": {
            "Earthquakes and Tsunamis": {
                "Causes of Earthquakes and Seismic Zones": [],
                "Tsunamis: Formation and Impact": [],
                "Earthquake Vulnerability in India": [],
            },
            "Cyclones and Tropical Storms": {
                "Formation and Types of Cyclones": [],
                "Cyclone Prone Areas of India": [],
                "Cyclone Warning and Management Systems": [],
            },
            "Volcanism and Landslides": {
                "Types of Volcanoes and Global Distribution": [],
                "Landslides: Causes and Risk Zones in India": [],
                "Climate-linked Geophysical Events": [],
            },
        },
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # GS PAPER II
    # ═══════════════════════════════════════════════════════════════════════════
    "Indian Polity & Constitution": {
        "Constitutional Framework": {
            "Historical Background of the Indian Constitution": {
                "Constitutional Development Under British Rule": [],
                "Government of India Acts: 1919 and 1935": [],
                "Constituent Assembly: Composition and Working": [],
                "Sources of the Indian Constitution": [],
            },
            "Preamble to the Constitution": {
                "Meaning and Significance of the Preamble": [],
                "Key Words: Sovereign, Socialist, Secular, Democratic, Republic": [],
                "Preamble and the Basic Structure Doctrine": [],
                "42nd Amendment and Changes to the Preamble": [],
            },
            "Salient Features of the Indian Constitution": {
                "Federal System with Unitary Bias": [],
                "Parliamentary System of Government": [],
                "Written, Rigid and Partly Flexible Constitution": [],
                "Independent Judiciary and Judicial Review": [],
                "Fundamental Law and Supremacy of Constitution": [],
            },
            "Union and Its Territory": {
                "Organisation of States and Union Territories": [],
                "Admission and Formation of New States": [],
                "Inter-State Boundaries and Disputes": [],
            },
        },
        "Citizenship and Fundamental Rights": {
            "Citizenship in India": {
                "Acquisition and Loss of Citizenship": [],
                "Single Citizenship in India": [],
                "NRI, PIO and OCI Status": [],
            },
            "Fundamental Rights": {
                "Right to Equality: Articles 14 to 18": [],
                "Right to Freedom: Articles 19 to 22": [],
                "Right Against Exploitation and Right to Religion": [],
                "Cultural, Educational Rights and Right to Constitutional Remedies": [],
                "Writs: Habeas Corpus, Mandamus, Certiorari, Prohibition, Quo Warranto": [],
            },
            "Directive Principles of State Policy": {
                "Classification of DPSPs": [],
                "Relationship Between Fundamental Rights and DPSPs": [],
                "Implementation and Constitutional Significance": [],
            },
            "Fundamental Duties": {
                "List and Significance of Fundamental Duties": [],
                "Legal Enforceability of Fundamental Duties": [],
                "Relationship Between Rights and Duties": [],
            },
            "Amendment of the Constitution": {
                "Types of Constitutional Amendments": [],
                "Procedure Under Article 368": [],
                "Major Constitutional Amendments and Their Impact": [],
            },
        },
        "Federal Structure": {
            "Basic Structure Doctrine": {
                "Kesavananda Bharati Case and Its Significance": [],
                "Elements of Basic Structure": [],
                "Evolution of Basic Structure Doctrine": [],
            },
            "Federal System in India": {
                "Features of Indian Federalism": [],
                "Cooperative and Competitive Federalism": [],
                "Asymmetric Federalism and Special Provisions": [],
            },
            "Centre-State Relations": {
                "Legislative Relations Between Centre and States": [],
                "Administrative Relations Between Centre and States": [],
                "Financial Relations Between Centre and States": [],
            },
            "Inter-State Relations": {
                "Inter-State Water Disputes": [],
                "Inter-State Trade and Commerce": [],
                "Interstate Council and Zonal Councils": [],
            },
            "Emergency Provisions": {
                "National Emergency Under Article 352": [],
                "President's Rule Under Article 356": [],
                "Financial Emergency and Safeguards Against Misuse": [],
            },
        },
        "Parliament and State Legislatures": {
            "Parliament: Structure and Composition": {
                "Lok Sabha: Composition, Election and Powers": [],
                "Rajya Sabha: Composition, Election and Powers": [],
                "Speaker and Deputy Speaker of Lok Sabha": [],
            },
            "Parliament: Functioning and Legislative Procedure": {
                "Sessions of Parliament and Important Procedures": [],
                "Legislative Procedure for Ordinary Bills": [],
                "Money Bills, Finance Bills and Joint Sitting": [],
                "Question Hour, Zero Hour and Adjournment Motion": [],
            },
            "Parliamentary Committees": {
                "Standing Committees and Their Functions": [],
                "Financial Committees: PAC, Estimates, Public Undertakings": [],
                "Ad-hoc Committees and Their Role": [],
            },
            "Anti-Defection Law": {
                "Tenth Schedule: Grounds for Disqualification": [],
                "Role of Speaker in Anti-Defection Cases": [],
                "Judicial Review of Anti-Defection Decisions": [],
            },
            "State Legislatures": {
                "Unicameral vs Bicameral State Legislatures": [],
                "Powers and Limitations of State Legislatures": [],
                "Relations Between State Legislature and Centre": [],
            },
        },
        "Executive": {
            "President of India": {
                "Election and Removal of the President": [],
                "Executive, Legislative and Judicial Powers of President": [],
                "Emergency Powers and Position in Parliamentary Democracy": [],
            },
            "Vice-President of India": {
                "Election and Functions of the Vice-President": [],
                "Role as Chairman of Rajya Sabha": [],
            },
            "Prime Minister and Council of Ministers": {
                "Appointment and Removal of Prime Minister": [],
                "Powers and Functions of the Prime Minister": [],
                "Cabinet System and Collective Responsibility": [],
            },
            "Governor": {
                "Appointment and Removal of Governor": [],
                "Powers and Functions of Governor": [],
                "Discretionary Powers and Controversies": [],
            },
            "Chief Minister and State Executive": {
                "Role and Powers of Chief Minister": [],
                "State Council of Ministers": [],
                "Relations Between Chief Minister and Governor": [],
            },
            "Pressure Groups and Civil Society": {
                "Types and Role of Pressure Groups in India": [],
                "Formal and Informal Associations in Polity": [],
                "Lobbying and Its Implications": [],
            },
        },
        "Judiciary": {
            "Supreme Court of India": {
                "Composition and Appointment of Judges": [],
                "Original, Appellate and Advisory Jurisdiction": [],
                "Independence of the Supreme Court": [],
            },
            "Judicial Review": {
                "Concept and Scope of Judicial Review in India": [],
                "Judicial Review in India vs USA": [],
                "Limitations on Judicial Review": [],
            },
            "Judicial Activism and PIL": {
                "Judicial Activism: Concept and Cases": [],
                "Public Interest Litigation in India": [],
                "Judicial Overreach: Debate and Concerns": [],
            },
            "High Courts and Subordinate Courts": {
                "Structure and Jurisdiction of High Courts": [],
                "District Courts and Lower Judiciary": [],
                "Appointment and Transfer of High Court Judges": [],
            },
            "Separation of Powers": {
                "Theory and Practice of Separation of Powers in India": [],
                "Checks and Balances Among Organs of Government": [],
                "Disputes Between Legislature, Executive and Judiciary": [],
            },
        },
        "Constitutional Bodies": {
            "Election Commission of India": {
                "Composition and Constitutional Independence": [],
                "Powers and Functions of ECI": [],
                "Model Code of Conduct": [],
                "Electoral Reforms in India": [],
            },
            "UPSC and State Public Service Commissions": {
                "Functions and Powers of UPSC": [],
                "Independence and Role in Recruitment": [],
                "State PSCs and Their Functioning": [],
            },
            "Finance Commission": {
                "Constitutional Provisions for Finance Commission": [],
                "Devolution of Taxes: Vertical and Horizontal": [],
                "Recommendations of Recent Finance Commissions": [],
            },
            "CAG: Comptroller and Auditor General": {
                "Constitutional Provisions and Independence": [],
                "Role of CAG in Financial Accountability": [],
                "CAG Reports and Parliamentary Scrutiny": [],
            },
            "National Commissions for SC, ST and OBC": {
                "Constitutional Provisions and Mandate": [],
                "Powers, Functions and Jurisdiction": [],
                "Recent Issues and Challenges": [],
            },
        },
        "Statutory and Regulatory Bodies": {
            "NITI Aayog": {
                "Replacement of Planning Commission": [],
                "Structure, Functions and Role": [],
                "NITI Aayog and Cooperative Federalism": [],
            },
            "National Human Rights Commission": {
                "Composition and Powers of NHRC": [],
                "Jurisdiction and Limitations": [],
                "Effectiveness and Challenges": [],
            },
            "Central Information Commission": {
                "RTI Act 2005 and Role of CIC": [],
                "Powers and Functions of CIC": [],
                "Challenges to RTI Implementation": [],
            },
            "Central Vigilance Commission": {
                "Structure and Functions of CVC": [],
                "Jurisdiction and Independence": [],
                "CVC and Anti-Corruption Framework": [],
            },
            "CBI: Central Bureau of Investigation": {
                "Legal Basis and Jurisdiction of CBI": [],
                "Functions and Roles of CBI": [],
                "Controversies and Reform Proposals": [],
            },
            "Lokpal and Lokayuktas": {
                "Constitutional and Legal Basis for Lokpal": [],
                "Structure, Jurisdiction and Powers": [],
                "Effectiveness of Lokpal in India": [],
            },
        },
        "Electoral System": {
            "Representation of People's Act": {
                "Salient Provisions of RPA 1950 and 1951": [],
                "Delimitation of Constituencies": [],
                "Electoral Offences and Disqualifications": [],
            },
            "Electoral Reforms in India": {
                "Key Electoral Reforms Implemented": [],
                "Pending Reforms and Recommendations": [],
                "Electoral Funding and Transparency": [],
            },
        },
    },
    "Governance & Social Justice": {
        "Governance Concepts": {
            "Governance vs Government": {
                "Concept and Evolution of Governance": [],
                "Good Governance Principles and Indicators": [],
                "Governance Deficit in India": [],
            },
            "Transparency and Accountability": {
                "RTI Act: Features, Impact and Challenges": [],
                "Social Audit as Accountability Tool": [],
                "Citizen's Charter and Service Delivery": [],
                "Whistleblower Protection in India": [],
            },
            "E-Governance": {
                "Digital India Initiative and Its Components": [],
                "E-governance Models and Global Examples": [],
                "Challenges in E-governance Implementation": [],
            },
            "Civil Services in India": {
                "Constitutional Provisions for Civil Services": [],
                "All India Services: IAS, IPS, IFS": [],
                "Civil Service Reforms and Lateral Entry": [],
            },
        },
        "Development Processes and Institutions": {
            "NGOs and Civil Society": {
                "Role of NGOs in Development": [],
                "FCRA and Regulation of Foreign Funding": [],
                "Challenges Faced by Civil Society": [],
            },
            "SHGs and Microfinance": {
                "Self-Help Group Model in India": [],
                "Microfinance: Concept and Impact": [],
                "SHGs and Rural Women Empowerment": [],
            },
            "Decentralisation and Local Governance": {
                "73rd Amendment and Panchayati Raj": [],
                "74th Amendment and Urban Local Bodies": [],
                "Devolution of Powers and Challenges": [],
            },
        },
        "Social Justice": {
            "Welfare Schemes for Vulnerable Sections": {
                "Schemes for SC, ST and OBC Communities": [],
                "Schemes for Women and Children": [],
                "Schemes for Elderly and Persons with Disability": [],
                "Schemes for Minorities and Economically Weaker Sections": [],
            },
            "Health Policy and Healthcare System": {
                "National Health Policy and Its Evolution": [],
                "Ayushman Bharat: PM-JAY and HWCs": [],
                "Public Health Infrastructure Challenges": [],
            },
            "Education Policy": {
                "National Education Policy 2020": [],
                "Right to Education Act and Implementation": [],
                "Higher Education Challenges in India": [],
            },
            "Poverty Alleviation Programmes": {
                "MGNREGA: Implementation and Impact": [],
                "National Food Security Act and PDS": [],
                "PM Awas Yojana and Housing for All": [],
            },
            "Police and Judicial Reforms": {
                "Police Reforms: Prakash Singh Case and Beyond": [],
                "Prison Reforms and Undertrial Prisoners": [],
                "Judicial Reforms and Pendency of Cases": [],
            },
        },
    },
    "International Relations": {
        "India's Foreign Policy": {
            "Evolution of India's Foreign Policy": {
                "Nehruvian Foreign Policy and Non-Alignment": [],
                "Post-Cold War Shifts in Indian Foreign Policy": [],
                "Contemporary Foreign Policy under Modi": [],
            },
            "India and the USA": {
                "Bilateral Relations: Historical Overview": [],
                "Defence and Strategic Partnership": [],
                "Trade, Technology and People-to-People Ties": [],
            },
            "India and China": {
                "Historical Relations and Border Disputes": [],
                "Economic Relations and Trade Imbalance": [],
                "Competition, Cooperation and Rivalry": [],
            },
            "India and Russia": {
                "Historical Strategic Partnership": [],
                "Defence Cooperation and Arms Transfers": [],
                "Contemporary Challenges in India-Russia Relations": [],
            },
            "India and Pakistan": {
                "Historical Context and Partition Legacy": [],
                "Kashmir Issue and Cross-border Terrorism": [],
                "Peace Initiatives and Current Status": [],
            },
        },
        "Neighbourhood Relations": {
            "India and Bangladesh": {
                "Bilateral Cooperation and Connectivity": [],
                "Water-sharing and Trade": [],
                "Challenges and Recent Developments": [],
            },
            "India and Nepal": {
                "Historical Ties and Special Relationship": [],
                "Border Issues and Recent Tensions": [],
                "Economic and Cultural Cooperation": [],
            },
            "India and Sri Lanka": {
                "Tamil Issue and Ethnic Conflict": [],
                "Strategic Interests and China Factor": [],
                "Bilateral Cooperation and Trade": [],
            },
            "India and Bhutan": {
                "Special Relationship and Treaty": [],
                "Hydropower Cooperation": [],
                "China Factor in India-Bhutan Relations": [],
            },
            "India, Maldives and Afghanistan": {
                "India-Maldives: India First Policy and Security": [],
                "India-Afghanistan: Post-Taliban Situation": [],
                "Indian Strategic Interests in the Region": [],
            },
        },
        "Regional and Global Groupings": {
            "SAARC and BIMSTEC": {
                "SAARC: Structure, Objectives and Challenges": [],
                "BIMSTEC as an Alternative to SAARC": [],
                "India's Approach to South Asian Regionalism": [],
            },
            "ASEAN and East Asia": {
                "India's Act East Policy": [],
                "India-ASEAN Strategic Partnership": [],
                "Quad and Indo-Pacific Strategy": [],
            },
            "SCO, BRICS and G20": {
                "India in the Shanghai Cooperation Organisation": [],
                "BRICS: Role and Significance for India": [],
                "G20 and India's Global Leadership": [],
            },
        },
        "International Institutions": {
            "United Nations System": {
                "UN Charter, Structure and Principal Organs": [],
                "UN Security Council Reform": [],
                "India and UN Peacekeeping Operations": [],
            },
            "WTO and Global Trade": {
                "WTO Structure and Key Agreements": [],
                "India's Trade Disputes at WTO": [],
                "Doha Development Round Issues": [],
            },
            "World Bank and IMF": {
                "Functions of World Bank and India's Relations": [],
                "IMF: Role, Conditionalities and Reforms": [],
                "India's Quota and Voting Rights": [],
            },
            "Indian Diaspora": {
                "Global Distribution of Indian Diaspora": [],
                "Economic Contributions and Remittances": [],
                "Diaspora Diplomacy and India's Soft Power": [],
            },
        },
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # GS PAPER III
    # ═══════════════════════════════════════════════════════════════════════════
    "Indian Economy": {
        "Macroeconomics and National Income": {
            "National Income Accounting": {
                "GDP, GNP, NNP: Concepts and Methods": [],
                "GDP at Factor Cost vs Market Price": [],
                "Debates Around GDP as a Welfare Measure": [],
            },
            "Inflation and Price Stability": {
                "Types and Causes of Inflation": [],
                "Measurement: CPI, WPI and GDP Deflator": [],
                "Monetary and Fiscal Anti-Inflationary Measures": [],
            },
            "Employment and Labour Market": {
                "Types of Unemployment in India": [],
                "Labour Market Reforms and Four Labour Codes": [],
                "Employment Schemes: MGNREGA and Others": [],
            },
            "Indian Economic Planning": {
                "Five-Year Plans: Evolution and Achievements": [],
                "NITI Aayog Replacing Planning Commission": [],
                "Post-Reform Economic Strategy": [],
            },
        },
        "Money, Banking and Finance": {
            "Money and Banking System": {
                "Money Supply: M0, M1, M2, M3": [],
                "Functions and Role of Reserve Bank of India": [],
                "Commercial Banking System and NPAs": [],
                "Financial Inclusion: Jan Dhan and Beyond": [],
            },
            "Monetary Policy": {
                "Monetary Policy Tools and Instruments": [],
                "Monetary Policy Committee and Inflation Targeting": [],
                "Transmission of Monetary Policy": [],
            },
            "Capital Markets and Investment": {
                "Stock Markets: BSE and NSE": [],
                "SEBI: Functions and Investor Protection": [],
                "FDI and FPI: Concepts and Policy": [],
                "Investment Models: PPP, BOT, BOOT": [],
            },
            "Government Budget and Fiscal Policy": {
                "Budget: Structure, Components and Process": [],
                "Direct and Indirect Taxes in India": [],
                "Fiscal Deficit, Revenue Deficit and FRBM Act": [],
                "GST: Features, Structure and Impact": [],
            },
        },
        "Agriculture": {
            "Cropping Patterns and Agricultural Seasons": {
                "Kharif, Rabi and Zaid Crops": [],
                "Major Crops and Their Distribution": [],
                "Agro-Climatic Zones of India": [],
            },
            "Agricultural Reforms and Policy": {
                "Land Reforms in India: Tenancy and Ceiling Acts": [],
                "Green Revolution: Impact and Criticism": [],
                "Farm Laws Controversy and APMC Reforms": [],
            },
            "Agricultural Marketing and MSP": {
                "MSP: Concept, Coverage and Controversy": [],
                "Public Distribution System and Food Security": [],
                "eNAM and Agricultural Marketing Reforms": [],
                "Food Corporation of India": [],
            },
            "Food Processing Industry": {
                "Scope and Significance of Food Processing": [],
                "Supply Chain Management in Agriculture": [],
                "Government Schemes for Food Processing": [],
            },
            "Allied Sectors": {
                "Animal Husbandry and Dairy Sector": [],
                "Fisheries Sector: Inland and Marine": [],
                "Apiculture and Other Allied Activities": [],
            },
        },
        "Liberalisation and Industrial Policy": {
            "Economic Reforms of 1991": {
                "LPG Reforms: Liberalisation, Privatisation, Globalisation": [],
                "Impact of 1991 Reforms on Indian Economy": [],
                "Post-Reform Growth Story and Challenges": [],
            },
            "Industrial Policy and Manufacturing": {
                "Industrial Policy Evolution in India": [],
                "Make in India and PLI Schemes": [],
                "MSME Sector: Role and Challenges": [],
                "Industrial Corridors and Manufacturing Hubs": [],
            },
            "Service Sector": {
                "IT and BPO Industry in India": [],
                "Banking, Insurance and Financial Services": [],
                "Tourism and Hospitality Sector": [],
            },
            "International Trade and Balance of Payments": {
                "India's Trade Policy and Export Promotion": [],
                "Current Account Deficit and Management": [],
                "Exchange Rate Management and Currency": [],
                "WTO, IMF and World Bank Impact on India": [],
            },
        },
        "Infrastructure and Inclusive Growth": {
            "Energy Sector": {
                "Power Generation Mix in India": [],
                "Renewable Energy Targets and Progress": [],
                "Energy Security Challenges": [],
            },
            "Transport Infrastructure": {
                "Road and National Highway Development": [],
                "Railway Modernisation: Vande Bharat and Bullet Train": [],
                "Port, Waterway and Aviation Development": [],
            },
            "Inclusive Growth": {
                "Concept of Inclusive Growth and Indicators": [],
                "Challenges to Inclusion in India": [],
                "Government Initiatives for Inclusive Development": [],
            },
        },
    },
    "Science & Technology": {
        "Space Technology": {
            "ISRO and India's Space Programme": {
                "History and Milestones of ISRO": [],
                "Launch Vehicles: PSLV, GSLV and LVM3": [],
                "Chandrayaan, Mangalyaan and Gaganyaan": [],
                "Commercial Space: New Space India Limited": [],
            },
            "Satellite Applications": {
                "Remote Sensing Satellites and Applications": [],
                "Communication Satellites: INSAT and GSAT": [],
                "Navigation Systems: NavIC": [],
            },
        },
        "Defence and Nuclear Technology": {
            "Defence Technology and DRDO": {
                "DRDO: Role and Key Programmes": [],
                "Missile Technology: Agni, Prithvi, BrahMos": [],
                "Indigenisation of Defence Production": [],
            },
            "Nuclear Technology": {
                "India's Civil Nuclear Programme": [],
                "Nuclear Doctrine: No-First Use Policy": [],
                "Nuclear Energy: Thorium Programme": [],
                "India and Nuclear Non-Proliferation Regime": [],
            },
        },
        "Emerging Technologies": {
            "Biotechnology": {
                "Genetic Engineering and Recombinant DNA Technology": [],
                "GM Crops: Benefits, Risks and Regulation": [],
                "Medical Biotechnology and Drug Development": [],
                "Bioethics and Biosafety Concerns": [],
            },
            "Artificial Intelligence and Robotics": {
                "AI Concepts and Applications in Governance": [],
                "Ethical Issues in AI and Bias": [],
                "India's National AI Strategy": [],
                "Robotics and Automation: Impact on Employment": [],
            },
            "Nanotechnology": {
                "Concepts and Applications of Nanotechnology": [],
                "Challenges, Risks and Safety Concerns": [],
                "Indian Nanotechnology Initiatives": [],
            },
        },
        "IT, Cyber Security and Communication": {
            "Information Technology and Digital India": {
                "IT Revolution and India's Software Industry": [],
                "Digital India: Key Pillars and Achievements": [],
                "Data Protection and Privacy Laws": [],
            },
            "Cyber Security": {
                "Types of Cyber Threats and Vulnerabilities": [],
                "Critical Infrastructure Protection": [],
                "National Cyber Security Policy and Frameworks": [],
                "IT Act 2000 and Amendments": [],
            },
            "Internet Governance and Social Media": {
                "Internet Governance: ICANN and Multi-stakeholder Model": [],
                "Social Media Regulation in India": [],
                "Fake News, Misinformation and Fact-checking": [],
            },
        },
        "Health and Agricultural Technology": {
            "Medical Technology and Innovations": {
                "Drug Discovery and Pharmaceutical Innovation": [],
                "Medical Devices and Diagnostics": [],
                "Telemedicine and Digital Health": [],
            },
            "Agricultural Technology": {
                "Precision Agriculture and Drones": [],
                "Biotechnology in Agriculture": [],
                "Genome Editing: CRISPR and Applications": [],
            },
            "Intellectual Property Rights": {
                "Patents, Trademarks and Copyrights": [],
                "IPR in India: Patents Act and TRIPS": [],
                "Traditional Knowledge and Biodiversity Protection": [],
            },
        },
    },
    "Environment & Ecology": {
        "Biodiversity and Conservation": {
            "Ecosystem Concepts": {
                "Types of Ecosystems and Their Features": [],
                "Food Chains, Food Webs and Energy Flow": [],
                "Ecosystem Services and Their Valuation": [],
                "Ecological Succession": [],
            },
            "Biodiversity: Types and Importance": {
                "Genetic, Species and Ecosystem Diversity": [],
                "Biodiversity Hotspots in India": [],
                "IUCN Red List and Categories": [],
            },
            "Threats to Biodiversity": {
                "Habitat Loss and Fragmentation": [],
                "Invasive Alien Species": [],
                "Poaching, Illegal Wildlife Trade and Bio-piracy": [],
            },
            "Conservation Strategies": {
                "In-situ Conservation: National Parks and Sanctuaries": [],
                "Ex-situ Conservation: Zoos, Gene Banks": [],
                "Community-based Conservation and Buffer Zones": [],
            },
            "Wildlife Protection": {
                "Wildlife Protection Act 1972 and Amendments": [],
                "Project Tiger and Project Elephant": [],
                "CITES, CBD and International Conservation Conventions": [],
            },
            "Biosphere Reserves and Wetlands": {
                "Biosphere Reserves in India": [],
                "Ramsar Sites and Wetland Conservation": [],
                "Mangroves, Coral Reefs and Coastal Ecosystems": [],
            },
        },
        "Environmental Pollution": {
            "Air Pollution": {
                "Sources and Types of Air Pollutants": [],
                "Air Quality Index and Health Impacts": [],
                "Control Measures and National Clean Air Programme": [],
            },
            "Water Pollution": {
                "Sources and Types of Water Pollution": [],
                "River Pollution: Ganga, Yamuna and Others": [],
                "Groundwater Contamination and Arsenic Crisis": [],
                "Water Treatment Technologies": [],
            },
            "Soil and Land Degradation": {
                "Causes of Soil Erosion and Degradation": [],
                "Desertification and Land Restoration": [],
                "Sustainable Land Management": [],
            },
            "Solid and Hazardous Waste": {
                "Municipal Solid Waste and Swachh Bharat Mission": [],
                "E-waste: Magnitude and Management": [],
                "Medical Waste Management": [],
            },
        },
        "Climate Change": {
            "Climate Change Science": {
                "Greenhouse Effect and Global Warming": [],
                "GHGs: CO2, Methane, Nitrous Oxide": [],
                "Climate Models and Future Projections": [],
            },
            "International Climate Agreements": {
                "UNFCCC and Kyoto Protocol": [],
                "Paris Agreement: Key Provisions and NDCs": [],
                "COP Meetings: Key Decisions and Outcomes": [],
                "Kigali Amendment and Montreal Protocol": [],
            },
            "Climate Change Impact on India": {
                "Monsoon Variability and Extreme Weather Events": [],
                "Sea Level Rise and Coastal Vulnerability": [],
                "Impact on Agriculture and Water Resources": [],
            },
            "Mitigation and Adaptation": {
                "Renewable Energy and Decarbonisation": [],
                "Carbon Markets and Carbon Pricing": [],
                "National Action Plan on Climate Change: 8 Missions": [],
                "Loss and Damage: Global Climate Justice": [],
            },
        },
        "Environmental Laws and Governance": {
            "Key Environmental Laws in India": {
                "Environment Protection Act 1986": [],
                "Forest Conservation Act and Forest Rights Act": [],
                "Coastal Regulation Zone Notifications": [],
            },
            "Environmental Impact Assessment": {
                "EIA Process: Stages and Procedure": [],
                "Public Hearing and Stakeholder Consultation": [],
                "EIA Amendments and Controversies": [],
            },
            "International Environmental Agreements": {
                "Basel, Rotterdam and Stockholm Conventions": [],
                "CBD and Nagoya Protocol on Access and Benefit Sharing": [],
                "Sustainable Development Goals and Environment": [],
            },
        },
    },
    "Internal Security": {
        "Terrorism and Extremism": {
            "Terrorism in India": {
                "Types and Patterns of Terrorism": [],
                "Major Terrorist Organisations Active in India": [],
                "Counter-terrorism Laws and Framework": [],
                "NIA and UAPA: Role and Controversies": [],
            },
            "Left-Wing Extremism: Naxalism": {
                "Historical Background of Naxal Movement": [],
                "Naxal-affected States and Spread": [],
                "Government's Dual Strategy: Development and Security": [],
            },
            "Insurgency in Northeast India": {
                "Historical Background of Insurgencies": [],
                "Major Groups: ULFA, NSCN and Others": [],
                "Peace Negotiations and Agreements": [],
            },
        },
        "Internal Security Challenges": {
            "Communal Violence and Riots": {
                "Causes and Patterns of Communal Violence": [],
                "Legal Framework for Prevention": [],
                "Role of Police and Administration": [],
            },
            "Cyber Security Threats": {
                "Cyber Threats: Hacking, Ransomware, Phishing": [],
                "Critical Infrastructure Protection": [],
                "National Cyber Security Policy and Frameworks": [],
            },
            "Money Laundering and Terror Financing": {
                "Methods and Mechanisms of Money Laundering": [],
                "PMLA: Prevention of Money Laundering Act": [],
                "FATF and International Cooperation": [],
            },
            "Organised Crime and Drug Trafficking": {
                "Organised Crime Networks in India": [],
                "Drug Trafficking Routes and Impact": [],
                "Legal Framework and Law Enforcement": [],
            },
        },
        "Border Management": {
            "India-Pakistan Border": {
                "Line of Control and International Border": [],
                "Cross-border Terrorism and Infiltration": [],
                "Border Management Initiatives and Smart Fencing": [],
            },
            "India-China Border": {
                "Line of Actual Control and Recent Standoffs": [],
                "Galwan and Doklam: Lessons and Implications": [],
                "Border Infrastructure Development": [],
            },
            "Coastal and Maritime Security": {
                "India's Coastal Security Framework": [],
                "Maritime Terrorism and Piracy": [],
                "Post-26/11 Coastal Security Reforms": [],
            },
        },
        "Security Forces and Intelligence": {
            "Armed Forces and Civil-Military Relations": {
                "Role of Army, Navy and Air Force": [],
                "Civil-Military Relations in India": [],
                "AFSPA: Armed Forces Special Powers Act": [],
                "Agnipath Scheme and Military Reforms": [],
            },
            "Central Armed Police Forces": {
                "CRPF, BSF, CISF, ITBP and SSB: Roles": [],
                "Coordination Between Forces": [],
            },
            "Intelligence Agencies": {
                "IB and RAW: Functions and Mandate": [],
                "Intelligence Failures and Reforms": [],
                "Parliamentary Oversight of Intelligence": [],
            },
        },
    },
    "Disaster Management": {
        "Disaster Risk and Classification": {
            "Types of Disasters and India's Vulnerability": {
                "Natural Disasters: Earthquakes, Floods, Cyclones": [],
                "Technological and Industrial Disasters": [],
                "India's Multi-hazard Vulnerability Profile": [],
            },
            "Disaster Risk Reduction": {
                "Concept and Framework for DRR": [],
                "Sendai Framework for DRR 2015-2030": [],
                "Community-based Disaster Risk Reduction": [],
            },
        },
        "Institutional Framework": {
            "Disaster Management Act and NDMA": {
                "Disaster Management Act 2005: Key Provisions": [],
                "NDMA: Structure and Functions": [],
                "NDRF: Capabilities and Deployment": [],
                "State and District Disaster Management Authorities": [],
            },
            "Disaster Management Cycle": {
                "Prevention and Mitigation Strategies": [],
                "Preparedness and Early Warning Systems": [],
                "Response Mechanisms and Relief Operations": [],
                "Recovery, Rehabilitation and Reconstruction": [],
            },
        },
        "Specific Hazards in India": {
            "Floods and Droughts": {
                "Flood Management: Causes and Strategies": [],
                "Drought Classification and Monitoring": [],
                "National Water Policy and Flood Control": [],
            },
            "Earthquakes and Tsunamis": {
                "Seismic Zones of India and Risk Assessment": [],
                "Earthquake-resistant Construction": [],
                "Indian Tsunami Early Warning System": [],
            },
            "Cyclones and Urban Disasters": {
                "Cyclone Preparedness and Warning Systems": [],
                "Odisha Cyclone Management Model": [],
                "Urban Floods and Heat Waves": [],
            },
        },
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # GS PAPER IV
    # ═══════════════════════════════════════════════════════════════════════════
    "Ethics, Integrity & Aptitude": {
        "Ethics and Human Values": {
            "Essence and Dimensions of Ethics": {
                "Meaning and Sources of Ethics": [],
                "Ethics in Private and Public Life": [],
                "Relationship Between Ethics, Morality and Law": [],
                "Dimensions of Ethics: Personal, Social, Political": [],
            },
            "Human Values and Great Leaders": {
                "Values from Indian Philosophical Traditions": [],
                "Lessons from Freedom Fighters and Reformers": [],
                "Values from Global Moral Leaders": [],
            },
            "Role of Family, Society and Education in Values": {
                "Family as the Primary Moral Institution": [],
                "Educational Institutions and Value Formation": [],
                "Media, Peer Groups and Value Erosion": [],
            },
        },
        "Attitude and Aptitude": {
            "Attitude: Concept and Components": {
                "Structure, Content and Function of Attitude": [],
                "Formation and Change of Attitudes": [],
                "Moral and Political Attitudes": [],
                "Social Influence and Persuasion": [],
            },
            "Emotional Intelligence": {
                "Components of EI: Self-Awareness and Empathy": [],
                "EI in Administration and Governance": [],
                "Developing Emotional Intelligence": [],
            },
            "Civil Service Aptitude and Values": {
                "Integrity, Impartiality and Non-partisanship": [],
                "Objectivity and Dedication to Public Service": [],
                "Compassion, Tolerance and Empathy": [],
            },
        },
        "Moral Thinking and Philosophy": {
            "Contributions of Indian Moral Thinkers": {
                "Gandhi: Satyagraha, Ahimsa and Trusteeship": [],
                "Ambedkar: Social Justice and Constitutional Ethics": [],
                "Vivekananda, Tilak and Gokhale on Ethics": [],
                "Kautilya's Arthashastra: Political Ethics": [],
            },
            "Contributions of Global Philosophers": {
                "Plato, Aristotle and Virtue Ethics": [],
                "Kant and Deontological Ethics": [],
                "Bentham and Mill: Utilitarianism": [],
                "Contemporary Moral Philosophy": [],
            },
            "Ethical Theories and Frameworks": {
                "Consequentialism and Its Applications": [],
                "Deontological Ethics in Practice": [],
                "Virtue Ethics and Character Development": [],
                "Applied Ethics: Medical, Environmental, Business": [],
            },
        },
        "Public Service Ethics": {
            "Ethics in Public Administration": {
                "Ethical Concerns in Government": [],
                "Codes of Conduct for Civil Servants": [],
                "Conflict of Interest and Its Management": [],
            },
            "Probity and Anti-Corruption": {
                "Concept of Probity in Governance": [],
                "Types and Impact of Corruption": [],
                "Prevention of Corruption Act and Mechanisms": [],
                "Vigilance Administration and CVC": [],
            },
            "Transparency and Accountability": {
                "RTI and Its Role in Accountability": [],
                "Citizen's Charter and Service Delivery": [],
                "Whistleblower Protection and Reporting": [],
            },
            "Ethics in International Relations": {
                "International Ethics and Human Rights": [],
                "India's Foreign Policy and Ethical Dimensions": [],
                "Global Justice, Equity and Responsibility": [],
            },
        },
        "Case Studies": {
            "Ethical Dilemmas in Civil Service": {
                "Nature of Ethical Dilemmas in Administration": [],
                "Decision-making Frameworks for Dilemmas": [],
                "Common Ethical Dilemma Scenarios": [],
            },
            "Situational Ethics and Leadership": {
                "Conflict of Interest in Public Service": [],
                "Ethical Leadership Under Pressure": [],
                "Crisis Management and Moral Courage": [],
            },
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# MANAGEMENT COMMAND
# ═══════════════════════════════════════════════════════════════════════════════


class Command(BaseCommand):
    help = (
        "Seeds the complete UPSC CSE syllabus hierarchy into knowledge_* tables. "
        "Fully idempotent — safe to re-run at any time."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--subject",
            type=str,
            default=None,
            help="Seed only this subject (exact name). Omit to seed all subjects.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print what would be created without writing to the database.",
        )

    def handle(self, *args, **options):
        target_subject = options.get("subject")
        dry_run = options.get("dry_run")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes.\n"))

        if not SYLLABUS:
            self.stdout.write(
                self.style.WARNING(
                    "SYLLABUS dict is empty. "
                    "Add subject data before running this command."
                )
            )
            return

        subjects_to_seed = (
            {target_subject: SYLLABUS[target_subject]}
            if target_subject and target_subject in SYLLABUS
            else SYLLABUS
        )

        if target_subject and target_subject not in SYLLABUS:
            self.stdout.write(
                self.style.ERROR(f"Subject '{target_subject}' not found in SYLLABUS.")
            )
            return

        # Ensure UPSC CSE program exists
        program = self._get_or_create_program(dry_run)

        total_subjects = total_modules = total_topics = 0
        total_subtopics = total_sub_subtopics = 0

        for subject_name, modules in subjects_to_seed.items():
            counts = self._seed_subject(subject_name, modules, program, dry_run)
            total_subjects += 1
            total_modules += counts["modules"]
            total_topics += counts["topics"]
            total_subtopics += counts["subtopics"]
            total_sub_subtopics += counts["sub_subtopics"]

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'[DRY RUN] ' if dry_run else ''}Seeding complete!\n"
                f"  Subjects      : {total_subjects}\n"
                f"  Modules       : {total_modules}\n"
                f"  Topics        : {total_topics}\n"
                f"  Subtopics     : {total_subtopics}\n"
                f"  Sub-subtopics : {total_sub_subtopics}\n"
                f"  TOTAL NODES   : {total_subjects + total_modules + total_topics + total_subtopics + total_sub_subtopics}"
            )
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # SEEDING HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _get_or_create_program(self, dry_run: bool):
        if dry_run:
            return None
        from engines.knowledge.models import Program

        program, created = Program.objects.get_or_create(
            name="UPSC CSE",
            defaults={"description": "UPSC Civil Services Examination"},
        )
        if created:
            self.stdout.write("  Created Program: UPSC CSE")
        return program

    def _seed_subject(
        self, subject_name: str, modules: dict, program, dry_run: bool
    ) -> dict:
        from engines.knowledge.models import Module, Subject, Topic

        counts = {"modules": 0, "topics": 0, "subtopics": 0, "sub_subtopics": 0}

        self.stdout.write(f"\nSeeding Subject: {subject_name}")

        if dry_run:
            for module_name, topics in modules.items():
                self.stdout.write(f"  [DRY] Module: {module_name}")
                counts["modules"] += 1
                for topic_name, subtopics in topics.items():
                    self.stdout.write(f"    [DRY] Topic: {topic_name}")
                    counts["topics"] += 1
                    for subtopic_name, sub_subtopics in subtopics.items():
                        self.stdout.write(f"      [DRY] Subtopic: {subtopic_name}")
                        counts["subtopics"] += 1
                        for ss_name in sub_subtopics:
                            self.stdout.write(f"        [DRY] Sub-subtopic: {ss_name}")
                            counts["sub_subtopics"] += 1
            return counts

        with transaction.atomic():
            # ── Subject ───────────────────────────────────────────────────────
            subject_obj, s_created = Subject.objects.get_or_create(
                name=subject_name,
                program=program,
                defaults={
                    "description": f"UPSC CSE subject: {subject_name}",
                    "is_active": True,
                },
            )

            for mod_idx, (module_name, topics) in enumerate(modules.items()):
                # ── Module ────────────────────────────────────────────────────
                module_obj, m_created = Module.objects.get_or_create(
                    name=module_name,
                    subject=subject_obj,
                    defaults={
                        "description": f"{module_name}",
                        "is_active": True,
                        "order_index": mod_idx,
                    },
                )
                counts["modules"] += 1

                for top_idx, (topic_name, subtopics) in enumerate(topics.items()):
                    # ── Topic ─────────────────────────────────────────────────
                    topic_obj, t_created = Topic.objects.get_or_create(
                        name=topic_name,
                        module=module_obj,
                        defaults={
                            "subject": subject_obj,
                            "is_active": True,
                            "topic_type": "syllabus",
                            "order_index": top_idx,
                        },
                    )
                    if t_created:
                        Topic.objects.filter(id=topic_obj.id).update(node_type="topic")
                    counts["topics"] += 1

                    for sub_idx, (subtopic_name, sub_subtopics) in enumerate(
                        subtopics.items()
                    ):
                        # ── Subtopic ──────────────────────────────────────────
                        subtopic_obj, st_created = Topic.objects.get_or_create(
                            name=subtopic_name,
                            module=module_obj,
                            defaults={
                                "subject": subject_obj,
                                "parent_topic": topic_obj,
                                "is_active": True,
                                "topic_type": "syllabus",
                                "order_index": sub_idx,
                            },
                        )
                        if st_created:
                            Topic.objects.filter(id=subtopic_obj.id).update(
                                node_type="subtopic"
                            )
                        counts["subtopics"] += 1

                        for ss_idx, ss_name in enumerate(sub_subtopics):
                            # ── Sub-subtopic ──────────────────────────────────
                            ss_obj, ss_created = Topic.objects.get_or_create(
                                name=ss_name,
                                module=module_obj,
                                defaults={
                                    "subject": subject_obj,
                                    "parent_topic": subtopic_obj,
                                    "is_active": True,
                                    "topic_type": "syllabus",
                                    "order_index": ss_idx,
                                },
                            )
                            if ss_created:
                                Topic.objects.filter(id=ss_obj.id).update(
                                    node_type="sub_subtopic"
                                )
                            counts["sub_subtopics"] += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"  ✅ {subject_name}: "
                f"{counts['modules']} modules, "
                f"{counts['topics']} topics, "
                f"{counts['subtopics']} subtopics, "
                f"{counts['sub_subtopics']} sub-subtopics"
            )
        )
        logger.info(
            "seed_syllabus_subject_complete",
            subject=subject_name,
            **counts,
        )
        return counts
