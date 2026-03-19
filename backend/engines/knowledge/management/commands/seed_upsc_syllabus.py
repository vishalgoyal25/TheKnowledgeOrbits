import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from engines.knowledge.models import (
    Program,
    Subject,
    Module,
    Topic,
    Theme,
    ThemeTopicMap,
    ChunkTopicMap,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Extremely Massive Seeding of the UPSC CSE Syllabus Hierarchy"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "Starting Extremely Massive UPSC Syllabus Seeding Process..."
            )
        )

        syllabus_data = [
            {
                "subject": {
                    "name": "Indian Heritage and Culture",
                    "desc": "Art Forms, Literature, and Architecture from ancient to modern times.",
                },
                "modules": [
                    {
                        "name": "Visual Arts & Architecture",
                        "desc": "Pre-historic, Indus Valley to Modern architecture.",
                        "topics": [
                            {
                                "name": "Ancient Architecture",
                                "desc": "Indus Valley, Mauryan, Post-Mauryan, Gupta.",
                                "diff": "medium",
                                "keys": ["architecture", "indus valley", "mauryan"],
                                "sub_topics": [
                                    {
                                        "name": "Buddhist Architecture",
                                        "desc": "Stupas, Viharas, Chaityas.",
                                        "diff": "medium",
                                        "keys": ["buddhism", "stupa"],
                                    },
                                    {
                                        "name": "Temple Architecture",
                                        "desc": "Nagara, Dravida, Vesara.",
                                        "diff": "hard",
                                        "keys": ["temple", "nagara", "dravida"],
                                    },
                                ],
                            },
                            {
                                "name": "Medieval & Indo-Islamic Architecture",
                                "desc": "Delhi Sultanate, Mughal architecture.",
                                "diff": "medium",
                                "keys": ["islamic", "mughal", "sultanate"],
                                "sub_topics": [
                                    {
                                        "name": "Mughal Architecture",
                                        "desc": "Taj Mahal, Red Fort, Fatehpur Sikri.",
                                        "diff": "easy",
                                        "keys": ["mughal", "taj mahal"],
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "name": "Performing Arts",
                        "desc": "Classical Music, Dance, Theatre.",
                        "topics": [
                            {
                                "name": "Classical Dances of India",
                                "desc": "Bharatanatyam, Kathak, Odissi, etc.",
                                "diff": "easy",
                                "keys": ["dance", "classical"],
                                "sub_topics": [
                                    {
                                        "name": "Bharatanatyam",
                                        "desc": "Features and exponents.",
                                        "diff": "medium",
                                        "keys": ["bharatanatyam", "tamil nadu"],
                                    },
                                    {
                                        "name": "Kathak",
                                        "desc": "Gharanas and features.",
                                        "diff": "medium",
                                        "keys": ["kathak", "gharanas"],
                                    },
                                ],
                            },
                            {
                                "name": "Indian Music",
                                "desc": "Hindustani, Carnatic, Folk.",
                                "diff": "medium",
                                "keys": ["music", "carnatic", "hindustani"],
                                "sub_topics": [
                                    {
                                        "name": "Hindustani Classical",
                                        "desc": "Ragas, Talas, Gharanas.",
                                        "diff": "hard",
                                        "keys": ["hindustani", "ragas"],
                                    }
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "Modern Indian History",
                    "desc": "Significant events, personalities, and issues from the middle of the 18th century.",
                },
                "modules": [
                    {
                        "name": "Advent of Europeans & British Expansion",
                        "desc": "Arrival of companies, Carnatic wars, Plassey.",
                        "topics": [
                            {
                                "name": "The British Conquest of India",
                                "desc": "Anglo-Mysore, Anglo-Maratha, and Sikh wars.",
                                "diff": "medium",
                                "keys": ["conquest", "british", "maratha"],
                                "sub_topics": [
                                    {
                                        "name": "Battle of Plassey & Buxar",
                                        "desc": "Causes and consequences.",
                                        "diff": "easy",
                                        "keys": ["plassey", "buxar", "bengal"],
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "name": "The Freedom Struggle",
                        "desc": "Stages and important contributors.",
                        "topics": [
                            {
                                "name": "The Revolt of 1857",
                                "desc": "Causes, events, and impact.",
                                "diff": "easy",
                                "keys": ["1857", "revolt", "mutiny"],
                                "sub_topics": [
                                    {
                                        "name": "Causes of the Revolt",
                                        "desc": "Political, Social, Economic factors.",
                                        "diff": "medium",
                                        "keys": ["causes", "enfield"],
                                    }
                                ],
                            },
                            {
                                "name": "Gandhian Phase (1915-1947)",
                                "desc": "Mass movements, non-cooperation, civil disobedience, Quit India.",
                                "diff": "medium",
                                "keys": ["gandhi", "freedom struggle"],
                                "sub_topics": [
                                    {
                                        "name": "Non-Cooperation Movement",
                                        "desc": "Chauri Chaura, Khilafat issue.",
                                        "diff": "easy",
                                        "keys": ["non-cooperation", "khilafat"],
                                    },
                                    {
                                        "name": "Civil Disobedience Movement",
                                        "desc": "Dandi March, Salt Satyagraha.",
                                        "diff": "medium",
                                        "keys": ["civil disobedience", "dandi"],
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "Ancient and Medieval History",
                    "desc": "Indus Valley Civilization to the Maratha Empire.",
                },
                "modules": [
                    {
                        "name": "Ancient India",
                        "desc": "Vedic Age, Mahajanapadas, Mauryan Empire.",
                        "topics": [
                            {
                                "name": "Indus Valley Civilization",
                                "desc": "Town planning, society, decline.",
                                "diff": "medium",
                                "keys": ["ivc", "harappa", "mohenjodaro"],
                                "sub_topics": [
                                    {
                                        "name": "Harappan Town Planning",
                                        "desc": "Drainage, citadel, great bath.",
                                        "diff": "medium",
                                        "keys": ["planning", "citadel"],
                                    }
                                ],
                            },
                            {
                                "name": "Mauryan Empire",
                                "desc": "Ashoka, Dhamma, administration.",
                                "diff": "hard",
                                "keys": ["maurya", "ashoka", "dhamma"],
                                "sub_topics": [],
                            },
                        ],
                    },
                    {
                        "name": "Medieval India",
                        "desc": "Delhi Sultanate, Mughal Empire, Marathas.",
                        "topics": [
                            {
                                "name": "Delhi Sultanate",
                                "desc": "Slave, Khilji, Tughlaq dynasties.",
                                "diff": "medium",
                                "keys": ["sultanate", "khilji"],
                                "sub_topics": [],
                            },
                            {
                                "name": "Mughal Empire",
                                "desc": "Akbar, Aurangzeb, administration.",
                                "diff": "hard",
                                "keys": ["mughal", "akbar", "mansabdari"],
                                "sub_topics": [
                                    {
                                        "name": "Mansabdari System",
                                        "desc": "Civil and military administration.",
                                        "diff": "hard",
                                        "keys": ["mansabdari", "military"],
                                    }
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "Geography of the World and India",
                    "desc": "Physical geography, resources, phenomena.",
                },
                "modules": [
                    {
                        "name": "Physical Geography",
                        "desc": "Geomorphology, Climatology, Oceanography.",
                        "topics": [
                            {
                                "name": "Geomorphology",
                                "desc": "Earth's interior, earthquakes, volcanoes.",
                                "diff": "medium",
                                "keys": ["earth", "geomorphology"],
                                "sub_topics": [
                                    {
                                        "name": "Plate Tectonics",
                                        "desc": "Continental drift, plate boundaries.",
                                        "diff": "hard",
                                        "keys": ["tectonics", "drift"],
                                    },
                                    {
                                        "name": "Volcanism & Earthquakes",
                                        "desc": "Causes, distribution, impact.",
                                        "diff": "medium",
                                        "keys": ["volcano", "earthquake"],
                                    },
                                ],
                            },
                            {
                                "name": "Climatology",
                                "desc": "Atmosphere, pressure, winds, cyclones.",
                                "diff": "hard",
                                "keys": ["climate", "atmosphere"],
                                "sub_topics": [
                                    {
                                        "name": "Tropical & Extratropical Cyclones",
                                        "desc": "Formation and characteristics.",
                                        "diff": "hard",
                                        "keys": ["cyclone", "tropical"],
                                    },
                                    {
                                        "name": "Indian Monsoon",
                                        "desc": "Mechanism, El Nino, La Nina.",
                                        "diff": "hard",
                                        "keys": ["monsoon", "el nino"],
                                    },
                                ],
                            },
                        ],
                    },
                    {
                        "name": "Indian Geography",
                        "desc": "Physiography, Drainage, Climate of India.",
                        "topics": [
                            {
                                "name": "Drainage System of India",
                                "desc": "Himalayan and Peninsular rivers.",
                                "diff": "medium",
                                "keys": ["rivers", "drainage"],
                                "sub_topics": [
                                    {
                                        "name": "Ganga River System",
                                        "desc": "Tributaries, dams, pollution.",
                                        "diff": "easy",
                                        "keys": ["ganga", "river"],
                                    },
                                    {
                                        "name": "Brahmaputra River System",
                                        "desc": "Course, flooding, significance.",
                                        "diff": "easy",
                                        "keys": ["brahmaputra", "assam"],
                                    },
                                ],
                            }
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "Indian Constitution and Polity",
                    "desc": "Historical underpinnings, evolution, features, amendments.",
                },
                "modules": [
                    {
                        "name": "Constitutional Framework",
                        "desc": "Historical background, making of the constitution.",
                        "topics": [
                            {
                                "name": "Historical Background",
                                "desc": "Regulating Acts to Government of India Acts.",
                                "diff": "hard",
                                "keys": ["acts", "british laws"],
                                "sub_topics": [
                                    {
                                        "name": "Government of India Act 1935",
                                        "desc": "Features and significance.",
                                        "diff": "medium",
                                        "keys": ["1935 act", "provincial autonomy"],
                                    }
                                ],
                            },
                            {
                                "name": "Fundamental Rights & Duties",
                                "desc": "Part III and Part IVA of the Constitution.",
                                "diff": "medium",
                                "keys": ["rights", "duties"],
                                "sub_topics": [
                                    {
                                        "name": "Article 21: Right to Life",
                                        "desc": "Evolution through Supreme Court judgments.",
                                        "diff": "hard",
                                        "keys": ["article 21", "life"],
                                    },
                                    {
                                        "name": "Freedom of Speech (Article 19)",
                                        "desc": "Reasonable restrictions and contemporary issues.",
                                        "diff": "hard",
                                        "keys": ["article 19", "speech"],
                                    },
                                ],
                            },
                        ],
                    },
                    {
                        "name": "System of Government",
                        "desc": "Parliamentary vs Presidential, Federal system.",
                        "topics": [
                            {
                                "name": "Parliament of India",
                                "desc": "Structure, functioning, conduct of business.",
                                "diff": "medium",
                                "keys": ["parliament", "lok sabha"],
                                "sub_topics": [
                                    {
                                        "name": "Law-Making Procedure",
                                        "desc": "Ordinary, Money, and Finance Bills.",
                                        "diff": "hard",
                                        "keys": ["bills", "law making"],
                                    },
                                    {
                                        "name": "Parliamentary Committees",
                                        "desc": "PAC, Estimates, Public Undertakings.",
                                        "diff": "medium",
                                        "keys": ["committees", "pac"],
                                    },
                                ],
                            }
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "Governance and Social Justice",
                    "desc": "Transparency, accountability, NGOs, vulnerable sections.",
                },
                "modules": [
                    {
                        "name": "Governance & Transparency",
                        "desc": "E-governace, RTI, Citizen Charters.",
                        "topics": [
                            {
                                "name": "Right to Information (RTI)",
                                "desc": "Act, challenges, and transparency.",
                                "diff": "medium",
                                "keys": ["rti", "transparency", "information"],
                                "sub_topics": [],
                            },
                            {
                                "name": "E-Governance",
                                "desc": "Models, successes, limitations.",
                                "diff": "easy",
                                "keys": ["egovernance", "digital india"],
                                "sub_topics": [
                                    {
                                        "name": "Direct Benefit Transfer (DBT)",
                                        "desc": "JAM trinity, leakages.",
                                        "diff": "medium",
                                        "keys": ["dbt", "jam"],
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "name": "Social Justice & Vulnerable Sections",
                        "desc": "Schemes, laws, performance.",
                        "topics": [
                            {
                                "name": "Women & Child Development",
                                "desc": "Schemes, malnutrition, empowerment.",
                                "diff": "medium",
                                "keys": ["women", "child", "malnutrition"],
                                "sub_topics": [],
                            }
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "International Relations",
                    "desc": "Bilateral, regional groupings, diaspora.",
                },
                "modules": [
                    {
                        "name": "India and its Neighborhood",
                        "desc": "Relations with Pakistan, China, Nepal, etc.",
                        "topics": [
                            {
                                "name": "India-China Relations",
                                "desc": "Border disputes, trade, Indo-Pacific.",
                                "diff": "hard",
                                "keys": ["china", "border", "indo-pacific"],
                                "sub_topics": [
                                    {
                                        "name": "Line of Actual Control (LAC)",
                                        "desc": "Standoffs and treaties.",
                                        "diff": "hard",
                                        "keys": ["lac", "standoff"],
                                    }
                                ],
                            },
                            {
                                "name": "India-Pakistan Relations",
                                "desc": "Kashmir issue, terrorism, Indus Water Treaty.",
                                "diff": "medium",
                                "keys": ["pakistan", "kashmir", "terrorism"],
                                "sub_topics": [],
                            },
                        ],
                    },
                    {
                        "name": "Global Groupings",
                        "desc": "UN, BRICS, QUAD, G20.",
                        "topics": [
                            {
                                "name": "The QUAD & Indo-Pacific",
                                "desc": "Significance, geopolitics, China containment.",
                                "diff": "medium",
                                "keys": ["quad", "indo-pacific"],
                                "sub_topics": [],
                            }
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "Indian Economy and Agriculture",
                    "desc": "Development, growth, inflation, agriculture.",
                },
                "modules": [
                    {
                        "name": "Macroeconomics & Banking",
                        "desc": "Inflation, Monetary Policy, Banking sector.",
                        "topics": [
                            {
                                "name": "Monetary Policy",
                                "desc": "RBI functions, rates, tools.",
                                "diff": "hard",
                                "keys": ["rbi", "monetary", "repo rate"],
                                "sub_topics": [
                                    {
                                        "name": "Inflation Targeting",
                                        "desc": "MPC, CPI vs WPI.",
                                        "diff": "medium",
                                        "keys": ["inflation", "cpi", "wpi"],
                                    }
                                ],
                            },
                            {
                                "name": "Banking Sector in India",
                                "desc": "Commercial banks, NPAs, reforms.",
                                "diff": "medium",
                                "keys": ["banking", "npa"],
                                "sub_topics": [
                                    {
                                        "name": "Non-Performing Assets (NPAs)",
                                        "desc": "Causes, IBC, Bad Banks.",
                                        "diff": "hard",
                                        "keys": ["npa", "ibc", "insolvency"],
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "name": "Agriculture & Food Security",
                        "desc": "Cropping patterns, irrigation, subsidies.",
                        "topics": [
                            {
                                "name": "Agricultural Subsidies & MSP",
                                "desc": "Direct/indirect subsidies, Minimum Support Price.",
                                "diff": "medium",
                                "keys": ["msp", "subsidy", "agriculture"],
                                "sub_topics": [
                                    {
                                        "name": "Public Distribution System (PDS)",
                                        "desc": "Objectives, functioning, limitations.",
                                        "diff": "medium",
                                        "keys": ["pds", "food security"],
                                    }
                                ],
                            }
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "Biodiversity and Environment",
                    "desc": "Climate Change, Conservation, Pollution.",
                },
                "modules": [
                    {
                        "name": "Ecology & Ecosystems",
                        "desc": "Basics of ecology, food chains, biomes.",
                        "topics": [
                            {
                                "name": "Ecosystem Dynamics",
                                "desc": "Energy flow, succession, ecological pyramids.",
                                "diff": "medium",
                                "keys": ["ecosystem", "ecology", "food web"],
                                "sub_topics": [],
                            }
                        ],
                    },
                    {
                        "name": "Climate Change & Treaties",
                        "desc": "Global warming, UNFCCC, protocols.",
                        "topics": [
                            {
                                "name": "International Environmental Conventions",
                                "desc": "Kyoto, Paris Agreement, CBD.",
                                "diff": "hard",
                                "keys": [
                                    "treaties",
                                    "climate change",
                                    "paris agreement",
                                ],
                                "sub_topics": [
                                    {
                                        "name": "UNFCCC & COP",
                                        "desc": "Conferences of Parties and climate finance.",
                                        "diff": "hard",
                                        "keys": ["cop", "unfccc", "finance"],
                                    }
                                ],
                            }
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "Science and Technology",
                    "desc": "Developments & Applications in everyday life.",
                },
                "modules": [
                    {
                        "name": "Space Technology",
                        "desc": "ISRO missions, satellite orbits.",
                        "topics": [
                            {
                                "name": "Indian Space Program",
                                "desc": "Chandrayaan, Gaganyaan, Aditya L1.",
                                "diff": "medium",
                                "keys": ["isro", "space", "satellite"],
                                "sub_topics": [
                                    {
                                        "name": "Types of Satellite Orbits",
                                        "desc": "LEO, MEO, GEO, Sun-synchronous.",
                                        "diff": "hard",
                                        "keys": ["orbits", "geo", "leo"],
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "name": "Emerging Technologies",
                        "desc": "AI, Nano, Biotech.",
                        "topics": [
                            {
                                "name": "Artificial Intelligence & Robotics",
                                "desc": "Machine learning, ethics of AI, industrial automation.",
                                "diff": "medium",
                                "keys": ["ai", "robotics", "machine learning"],
                                "sub_topics": [
                                    {
                                        "name": "Generative AI",
                                        "desc": "LLMs, Deepfakes, Regulations.",
                                        "diff": "medium",
                                        "keys": ["llm", "deepfake", "genai"],
                                    }
                                ],
                            },
                            {
                                "name": "Biotechnology",
                                "desc": "CRISPR, GM Crops, Stem cells.",
                                "diff": "hard",
                                "keys": ["crispr", "gm crops", "biotech"],
                                "sub_topics": [],
                            },
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "Internal Security and Disaster Management",
                    "desc": "Extremism, cyber security, borders.",
                },
                "modules": [
                    {
                        "name": "Internal Security Challenges",
                        "desc": "Terrorism, Naxalism, cyber threats.",
                        "topics": [
                            {
                                "name": "Left Wing Extremism (LWE)",
                                "desc": "Causes, spread, and government strategy (SAMADHAN).",
                                "diff": "medium",
                                "keys": ["naxalism", "lwe", "extremism"],
                                "sub_topics": [],
                            },
                            {
                                "name": "Cyber Security",
                                "desc": "Basics of cyber security, CERT-In, malware.",
                                "diff": "medium",
                                "keys": ["cyber", "hacker", "malware"],
                                "sub_topics": [
                                    {
                                        "name": "Critical Information Infrastructure",
                                        "desc": "NCIIPC, ransomware attacks on power grids/hospitals.",
                                        "diff": "hard",
                                        "keys": ["ci", "ransomware", "infrastructure"],
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "name": "Disaster Management",
                        "desc": "NDMA, Sendai Framework, disaster cycles.",
                        "topics": [
                            {
                                "name": "Natural Disasters",
                                "desc": "Floods, droughts, earthquakes mitigation.",
                                "diff": "easy",
                                "keys": ["disaster", "mitigation", "ndma"],
                                "sub_topics": [],
                            }
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "Ethics, Integrity and Aptitude",
                    "desc": "Moral philosophy, emotional intelligence, probity.",
                },
                "modules": [
                    {
                        "name": "Ethics and Human Interface",
                        "desc": "Essence, determinants and consequences.",
                        "topics": [
                            {
                                "name": "Dimensions of Ethics",
                                "desc": "Private vs Public relationships.",
                                "diff": "medium",
                                "keys": ["ethics", "values", "morals"],
                                "sub_topics": [
                                    {
                                        "name": "Ethics in Public Administration",
                                        "desc": "Dilemmas, accountability.",
                                        "diff": "hard",
                                        "keys": ["accountability", "dilemma"],
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "name": "Emotional Intelligence",
                        "desc": "Concepts, utilities in administration.",
                        "topics": [
                            {
                                "name": "EI in Civil Services",
                                "desc": "Empathy, tolerance, compassion.",
                                "diff": "medium",
                                "keys": ["ei", "empathy", "compassion"],
                                "sub_topics": [],
                            }
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "Indian Society and Social Issues",
                    "desc": "Diversity, vulnerable sections, and globalization.",
                },
                "modules": [
                    {
                        "name": "Salient Features of Indian Society",
                        "desc": "Diversity, Role of Women, Population.",
                        "topics": [
                            {
                                "name": "Diversity of India",
                                "desc": "Caste, Religion, Ethnicity.",
                                "diff": "easy",
                                "keys": ["diversity", "caste", "ethnicity"],
                                "sub_topics": [],
                            },
                            {
                                "name": "Role of Women",
                                "desc": "Women's organizations, SHGs.",
                                "diff": "medium",
                                "keys": ["women", "shg", "empowerment"],
                                "sub_topics": [
                                    {
                                        "name": "Issues related to Women",
                                        "desc": "Patriarchy, violence, laws.",
                                        "diff": "medium",
                                        "keys": ["patriarchy", "violence"],
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "name": "Social Dynamics",
                        "desc": "Globalization, Communalism, Regionalism, Secularism.",
                        "topics": [
                            {
                                "name": "Effects of Globalization on Indian Society",
                                "desc": "Impact on culture, economy.",
                                "diff": "hard",
                                "keys": ["globalization", "culture", "economy"],
                                "sub_topics": [],
                            }
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "Agriculture and Rural Development",
                    "desc": "Farming, MSP, Irrigation, Food Security.",
                },
                "modules": [
                    {
                        "name": "Farming Practices",
                        "desc": "Cropping patterns and irrigation.",
                        "topics": [
                            {
                                "name": "Major Cropping Patterns",
                                "desc": "Rabi, Kharif, Zaid.",
                                "diff": "medium",
                                "keys": ["crops", "rabi", "kharif"],
                                "sub_topics": [],
                            },
                            {
                                "name": "Irrigation Systems",
                                "desc": "Canal, drip, sprinkler irrigation.",
                                "diff": "easy",
                                "keys": ["irrigation", "water"],
                                "sub_topics": [],
                            },
                        ],
                    },
                    {
                        "name": "Agricultural Economics",
                        "desc": "Subsidies, MSP, PDS.",
                        "topics": [
                            {
                                "name": "Farm Subsidies & MSP",
                                "desc": "Issues with direct and indirect subsidies.",
                                "diff": "hard",
                                "keys": ["subsidy", "msp", "agriculture"],
                                "sub_topics": [],
                            }
                        ],
                    },
                ],
            },
            {
                "subject": {
                    "name": "World Geography",
                    "desc": "Major physical features of the world.",
                },
                "modules": [
                    {
                        "name": "Key Geographical Resources",
                        "desc": "Distribution of primary, secondary, tertiary resources.",
                        "topics": [
                            {
                                "name": "Distribution of Natural Resources",
                                "desc": "Coal, iron ore, petroleum globally.",
                                "diff": "hard",
                                "keys": ["resources", "coal", "petroleum"],
                                "sub_topics": [],
                            }
                        ],
                    }
                ],
            },
            {
                "subject": {
                    "name": "General Science",
                    "desc": "Basic physics, chemistry, and biology.",
                },
                "modules": [
                    {
                        "name": "Fundamentals of Biology",
                        "desc": "Cells, human body, diseases.",
                        "topics": [
                            {
                                "name": "Cell Biology",
                                "desc": "Structure and function of cells.",
                                "diff": "easy",
                                "keys": ["cell", "biology", "genetics"],
                                "sub_topics": [],
                            },
                            {
                                "name": "Human Diseases",
                                "desc": "Communicable and non-communicable diseases.",
                                "diff": "medium",
                                "keys": ["disease", "health", "virus"],
                                "sub_topics": [
                                    {
                                        "name": "Viral Diseases",
                                        "desc": "COVID, Dengue, HIV.",
                                        "diff": "medium",
                                        "keys": ["virus", "dengue", "covid"],
                                    }
                                ],
                            },
                        ],
                    }
                ],
            },
        ]

        with transaction.atomic():
            self.stdout.write("1. Cleaning all existing Knowledge Engine data...")
            ChunkTopicMap.objects.all().delete()
            ThemeTopicMap.objects.all().delete()
            Theme.objects.all().delete()
            Topic.objects.all().delete()
            Module.objects.all().delete()
            Subject.objects.all().delete()
            Program.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Database wiped clean."))

            self.stdout.write("2. Seeding UPSC Program...")
            program = Program.objects.create(
                name="UPSC Civil Services Examination",
                description="The comprehensive examination for Indian Civil Services.",
                exam_pattern={"stages": ["Prelims", "Mains", "Interview"]},
                is_active=True,
            )

            self.stdout.write(
                "3. Massively Seeding Subjects, Modules, Topics, and Sub-Topics..."
            )

            total_subjects = 0
            total_modules = 0
            total_topics = 0
            total_subtopics = 0

            # List to store all topics for Theme mapping
            created_topics_ref = []

            for s_idx, subj_data in enumerate(syllabus_data):
                subject = Subject.objects.create(
                    name=subj_data["subject"]["name"],
                    program=program,
                    description=subj_data["subject"]["desc"],
                    order_index=s_idx + 1,
                    is_active=True,
                )
                total_subjects += 1

                for m_idx, mod_data in enumerate(subj_data["modules"]):
                    module = Module.objects.create(
                        name=mod_data["name"],
                        subject=subject,
                        description=mod_data["desc"],
                        order_index=m_idx + 1,
                        is_active=True,
                    )
                    total_modules += 1

                    for t_idx, topic_data in enumerate(mod_data["topics"]):
                        topic = Topic.objects.create(
                            name=topic_data["name"],
                            module=module,
                            subject=subject,
                            parent_topic=None,  # Root Topic
                            description=topic_data["desc"],
                            keywords=topic_data["keys"],
                            topic_type="syllabus",
                            difficulty_level=topic_data["diff"],
                            order_index=t_idx + 1,
                            is_active=True,
                        )
                        total_topics += 1
                        created_topics_ref.append(topic)

                        # Create Sub-Topics if they exist (This populates parent_topic_id!)
                        for st_idx, sub_data in enumerate(
                            topic_data.get("sub_topics", [])
                        ):
                            sub_topic = Topic.objects.create(
                                name=sub_data["name"],
                                module=module,
                                subject=subject,
                                parent_topic=topic,  # THIS IS THE VITAL LINK!
                                description=sub_data["desc"],
                                keywords=sub_data["keys"],
                                topic_type="syllabus",
                                difficulty_level=sub_data["diff"],
                                order_index=st_idx + 1,
                                is_active=True,
                            )
                            total_subtopics += 1
                            created_topics_ref.append(sub_topic)

            self.stdout.write("4. Seeding Overarching cross-subject Themes...")
            themes_data = [
                {
                    "name": "Climate Change & Global Warming",
                    "desc": "Impacting geo, agriculture, and IR.",
                    "keys": ["climate", "monsoon", "treaties", "cop"],
                },
                {
                    "name": "Women Empowerment & Society",
                    "desc": "Role of women, SHGs, development.",
                    "keys": ["women", "society", "empowerment"],
                },
                {
                    "name": "Technological Disruptions",
                    "desc": "AI, space, cyber threats.",
                    "keys": ["ai", "cyber", "technology", "space"],
                },
                {
                    "name": "Economic Disparities & Growth",
                    "desc": "Poverty, banking sector reforms, and equitable growth.",
                    "keys": ["poverty", "banking", "npa"],
                },
                {
                    "name": "Democratic Decentralization",
                    "desc": "Panchayats, local bodies, structure.",
                    "keys": ["local government", "panchayat"],
                },
                {
                    "name": "National Security Architecture",
                    "desc": "LWE, borders, terrorism.",
                    "keys": ["security", "lwe", "extremism"],
                },
                {
                    "name": "Judicial Reforms & Activism",
                    "desc": "Supreme court, tribunals.",
                    "keys": ["supreme court", "article 21"],
                },
                {
                    "name": "Resource Security (Water/Energy)",
                    "desc": "Geopolitics of resources.",
                    "keys": ["resources", "energy", "water"],
                },
                {
                    "name": "Global South Leadership",
                    "desc": "India's role in developing nations.",
                    "keys": ["foreign policy", "diplomacy"],
                },
                {
                    "name": "Constitutional Amendments & Debates",
                    "desc": "Evolution of basic structure.",
                    "keys": ["amendment", "constitution"],
                },
                {
                    "name": "Agriculture & Rural Development",
                    "desc": "Poverty alleviation in rural India.",
                    "keys": ["agriculture", "poverty", "msp"],
                },
                {
                    "name": "Pandemics & Public Health",
                    "desc": "Post-COVID health resilience.",
                    "keys": ["health", "welfare"],
                },
                {
                    "name": "Urbanization & Smart Cities",
                    "desc": "Congestion, waste management, housing.",
                    "keys": ["urbanization", "cities"],
                },
                {
                    "name": "Indo-Pacific Geostrategy",
                    "desc": "QUAD, South China Sea, maritime security.",
                    "keys": ["indo-pacific", "quad"],
                },
                {
                    "name": "Digital Economy & Cryptocurrency",
                    "desc": "RBI digital rupee, CBDC, cashless.",
                    "keys": ["digital", "rbi", "cyber"],
                },
                {
                    "name": "Public Health & Sanitation",
                    "desc": "Swachh Bharat, Ayushman Bharat, malnutrition.",
                    "keys": ["health", "sanitation", "malnutrition"],
                },
                {
                    "name": "Space Exploration & Geopolitics",
                    "desc": "Militarization of space, satellite diplomacy.",
                    "keys": ["space", "satellite", "isro"],
                },
                {
                    "name": "Secularism & Communal Harmony",
                    "desc": "Religious diversity, tolerance, riots.",
                    "keys": ["secularism", "communalism", "diversity"],
                },
                {
                    "name": "Renewable Energy Transition",
                    "desc": "Solar, wind, EV policy, green hydrogen.",
                    "keys": ["renewable", "solar", "energy"],
                },
                {
                    "name": "Atmanirbhar Bharat & Indigenization",
                    "desc": "Self-reliance in defense and tech.",
                    "keys": ["atmanirbhar", "indigenization", "defense"],
                },
            ]

            total_themes = 0
            for t_data in themes_data:
                theme = Theme.objects.create(
                    name=t_data["name"], description=t_data["desc"], is_active=True
                )
                total_themes += 1

                # Map Theme to Topics based on keywords
                for topic in created_topics_ref:
                    for keyword in topic.keywords:
                        if keyword in t_data["keys"]:
                            ThemeTopicMap.objects.get_or_create(
                                theme=theme, topic=topic, defaults={"weight": 0.8}
                            )
                            break

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n>>> EXTREME MASSIVE SEED COMPLETE <<<\n"
                    f"- Programs: 1\n"
                    f"- Subjects: {total_subjects}\n"
                    f"- Modules: {total_modules}\n"
                    f"- Root Topics: {total_topics}\n"
                    f"- Sub-Topics: {total_subtopics}\n"
                    f"- Themes: {total_themes}\n"
                    f"Notice: parent_topic_id is securely populated for all {total_subtopics} Sub-Topics!"
                )
            )
