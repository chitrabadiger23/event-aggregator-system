import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_NAME = os.path.join(BASE_DIR, "events.db")
DUPLICATE_ID = 99
KEEP_ID = 7

def main():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, title, date, location, link FROM events WHERE id IN (?, ?)", (KEEP_ID, DUPLICATE_ID))
        rows = cursor.fetchall()
        print("=" * 70)
        print("DUPLICATE CLEANUP")
        print("=" * 70)
        if len(rows) != 2:
            print(f"Safety check failed. Expected IDs {KEEP_ID} and {DUPLICATE_ID}; found:")
            for row in rows: print(row)
            print("No changes were made.")
            return
        keep = next(row for row in rows if row[0] == KEEP_ID)
        duplicate = next(row for row in rows if row[0] == DUPLICATE_ID)
        print("\nKEEPING:")
        print(f"ID    : {keep[0]}\nTitle : {keep[1]}\nDate  : {keep[2]}\nVenue : {keep[3]}\nLink  : {keep[4]}")
        print("\nREMOVING:")
        print(f"ID    : {duplicate[0]}\nTitle : {duplicate[1]}\nDate  : {duplicate[2]}\nVenue : {duplicate[3]}\nLink  : {duplicate[4]}")
        expected_title = "Sri Krishna Janmashtami Ananda Mahotsava 2026 (4th & 5th September)"
        if duplicate[1] != expected_title:
            print("\nSafety check failed: ID 99 title is not the expected duplicate.")
            print("No changes were made.")
            return
        confirm = input("\nType DELETE 99 to continue: ").strip()
        if confirm != "DELETE 99":
            print("Cancelled. No changes were made.")
            return
        conn.execute("BEGIN")
        cursor.execute("DELETE FROM event_metadata WHERE event_id = ?", (DUPLICATE_ID,))
        metadata_deleted = cursor.rowcount
        cursor.execute("DELETE FROM events WHERE id = ?", (DUPLICATE_ID,))
        event_deleted = cursor.rowcount
        if event_deleted != 1:
            raise RuntimeError(f"Expected to delete exactly 1 event, deleted {event_deleted}.")
        conn.commit()
        print("\nDuplicate removed successfully.")
        print(f"Metadata rows removed: {metadata_deleted}")
        print(f"Event rows removed   : {event_deleted}")
        print(f"Kept event ID        : {KEEP_ID}")
        print(f"Removed event ID     : {DUPLICATE_ID}")
    except Exception as e:
        conn.rollback()
        print("\nCleanup failed. Transaction rolled back.")
        print(type(e).__name__ + ":", e)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
