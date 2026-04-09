import tempfile
import unittest
from pathlib import Path

from persistence import NullRunStore, build_run_store
from settings import Settings


class PersistenceTests(unittest.TestCase):
    def test_null_store_returns_empty_results(self) -> None:
        store = NullRunStore()

        best_run = store.best_run_for(mode_id="iteration", pack_id="lite")
        recorded = store.record_completed_run(
            mode_id="iteration",
            pack_id="lite",
            vocabulary_name="lite.txt",
            score=12,
            turns=5,
            elapsed_seconds=42,
            game_result="win",
            provider_label="fake-ranker",
            used_fallback=False,
        )

        self.assertIsNone(best_run)
        self.assertIsNone(recorded.run_record_id)
        self.assertFalse(recorded.is_new_best)

    def test_sqlite_run_store_records_and_returns_best_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "semantris.sqlite3"
            settings = Settings(
                semantris_persistence_backend="sqlite",
                semantris_database_url=f"sqlite:///{database_path}",
            )
            store = build_run_store(settings)

            first = store.record_completed_run(
                mode_id="iteration",
                pack_id="lite",
                vocabulary_name="lite.txt",
                score=12,
                turns=6,
                elapsed_seconds=45,
                game_result="win",
                provider_label="fake-ranker",
                used_fallback=False,
            )
            second = store.record_completed_run(
                mode_id="iteration",
                pack_id="lite",
                vocabulary_name="lite.txt",
                score=15,
                turns=7,
                elapsed_seconds=52,
                game_result="win",
                provider_label="fake-ranker",
                used_fallback=False,
            )

            self.assertTrue(first.is_new_best)
            self.assertTrue(second.is_new_best)
            self.assertIsNotNone(second.run_record_id)

            best_run = store.best_run_for(mode_id="iteration", pack_id="lite")
            self.assertIsNotNone(best_run)
            assert best_run is not None
            self.assertEqual(best_run.score, 15)
            self.assertEqual(best_run.run_record_id, second.run_record_id)


if __name__ == "__main__":
    unittest.main()
