from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "../data"
DB_LOCATION = Path(__file__).resolve().parent.parent / "chroma-langchain_db"


def _group_related_fields(eva_data, eva_name):
    """
    Group related telemetry fields into logical subsystems.
    Returns a list of documents with grouped context.
    """
    documents = []
    
    # Define subsystem groupings
    subsystems = {
        "oxygen_system": [
            "oxy_pri_storage", "oxy_sec_storage",
            "oxy_pri_pressure", "oxy_sec_pressure",
            "oxy_consumption", "suit_pressure_oxy"
        ],
        "power_system": [
            "primary_battery_level", "secondary_battery_level"
        ],
        "co2_removal": [
            "scrubber_a_co2_storage", "scrubber_b_co2_storage",
            "suit_pressure_co2", "helmet_pressure_co2",
            "co2_production", "fan_pri_rpm", "fan_sec_rpm"
        ],
        "cooling_system": [
            "coolant_storage", "coolant_gas_pressure",
            "coolant_liquid_pressure", "temperature"
        ],
        "biometrics": [
            "heart_rate", "suit_pressure_total", "suit_pressure_other"
        ],
        "mission_time": [
            "eva_elapsed_time"
        ]
    }
    
    # Create full telemetry document with all fields
    full_content = f"EVA {eva_name.upper()} - Complete Telemetry:\n"
    for key, value in eva_data.items():
        full_content += f"{key}: {value}\n"
    
    documents.append(Document(
        page_content=full_content,
        metadata={"type": "full_telemetry", "eva": eva_name},
        id=f"{eva_name}:full_telemetry"
    ))
    
    # Create subsystem-grouped documents
    for subsystem, fields in subsystems.items():
        content = f"EVA {eva_name.upper()} - {subsystem.replace('_', ' ').title()}:\n"
        for field in fields:
            if field in eva_data:
                content += f"{field}: {eva_data[field]}\n"
        
        if content.count(":") > 1:  # Only add if has multiple fields
            documents.append(Document(
                page_content=content,
                metadata={"type": "subsystem", "subsystem": subsystem, "eva": eva_name},
                id=f"{eva_name}:{subsystem}"
            ))
    
    return documents


def _load_documents_from_json(data_dir):
    """
    Load JSON files and create grouped documents.
    Returns documents grouped by subsystem and section for better retrieval.
    """
    all_documents = []
    all_ids = []

    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return [], []

    json_files = sorted(data_dir.glob("*.json"))
    if not json_files:
        logger.warning(f"No JSON files found in {data_dir}")
        return [], []

    for file_path in json_files:
        try:
            with file_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)

            # Handle telemetry structure
            if "telemetry" in payload:
                telemetry = payload["telemetry"]
                for eva_name, eva_data in telemetry.items():
                    documents = _group_related_fields(eva_data, eva_name)
                    all_documents.extend(documents)
                    all_ids.extend([doc.id for doc in documents])
            
            # Handle DCU section
            if "dcu" in payload:
                dcu = payload["dcu"]
                for eva_name, dcu_data in dcu.items():
                    content = f"EVA {eva_name.upper()} - Device Control Unit (DCU):\n"
                    for device, status in dcu_data.items():
                        if isinstance(status, dict):
                            status_str = ", ".join(f"{k}={v}" for k, v in status.items())
                        else:
                            status_str = str(status)
                        content += f"{device}: {status_str}\n"
                    
                    doc = Document(
                        page_content=content,
                        metadata={"type": "dcu", "eva": eva_name},
                        id=f"{eva_name}:dcu"
                    )
                    all_documents.append(doc)
                    all_ids.append(doc.id)
            
            # Handle error section
            if "error" in payload:
                error_data = payload["error"]
                content = "System Errors:\n"
                for error_name, status in error_data.items():
                    content += f"{error_name}: {status}\n"
                
                doc = Document(
                    page_content=content,
                    metadata={"type": "error"},
                    id="system:errors"
                )
                all_documents.append(doc)
                all_ids.append(doc.id)
            
            # Handle IMU section
            if "imu" in payload:
                imu = payload["imu"]
                for eva_name, imu_data in imu.items():
                    content = f"EVA {eva_name.upper()} - IMU (Position & Heading):\n"
                    for key, value in imu_data.items():
                        content += f"{key}: {value}\n"
                    
                    doc = Document(
                        page_content=content,
                        metadata={"type": "imu", "eva": eva_name},
                        id=f"{eva_name}:imu"
                    )
                    all_documents.append(doc)
                    all_ids.append(doc.id)
            
            # Handle UIA section
            if "uia" in payload:
                uia_data = payload["uia"]
                content = "External Equipment (UIA):\n"
                for device, status in uia_data.items():
                    content += f"{device}: {status}\n"
                
                doc = Document(
                    page_content=content,
                    metadata={"type": "uia"},
                    id="system:uia"
                )
                all_documents.append(doc)
                all_ids.append(doc.id)
            
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            continue

    return all_documents, all_ids


try:
    embeddings = OllamaEmbeddings(model="mxbai-embed-large")
    
    documents, ids = _load_documents_from_json(DATA_DIR)

    vector_store = Chroma(
        collection_name="telemetry",
        persist_directory=str(DB_LOCATION),
        embedding_function=embeddings,
    )

    existing = vector_store.get(include=[])
    existing_ids = set(existing.get("ids", []))

    new_documents = []
    new_ids = []
    for document, doc_id in zip(documents, ids):
        if doc_id not in existing_ids:
            new_documents.append(document)
            new_ids.append(doc_id)

    if new_documents:
        vector_store.add_documents(documents=new_documents, ids=new_ids)

    # Retrieve with dynamic k based on available documents
    retriever = vector_store.as_retriever(
        search_kwargs={"k": min(10, max(len(existing_ids), 5))}
    )
    
except Exception as e:
    logger.error(f"Failed to initialize vector store: {e}")
    raise