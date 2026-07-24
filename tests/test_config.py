from config import get_settings


def test_settings_load():
    settings = get_settings()

    assert settings.app_name == "CareerLens"
    assert settings.environment == "development"
    assert 0 <= settings.fallback_confidence_threshold <= 1


def test_storage_directories_created():
    settings = get_settings()

    assert settings.storage_root.exists()
    assert settings.documents_dir.exists()
    assert settings.metadata_dir.exists()
    assert settings.json_dir.exists()
    assert settings.embeddings_dir.exists()