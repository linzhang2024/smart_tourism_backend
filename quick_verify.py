import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from database import engine

Session = sessionmaker(bind=engine)


def main():
    print("=" * 60)
    print("Quick Database Verification")
    print("=" * 60)
    print("Time: {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    db = Session()
    
    try:
        result = db.execute(text("PRAGMA table_info(scenic_spots)"))
        columns = [row[1] for row in result]
        
        print("\nscenic_spots table columns:")
        for col in columns:
            print("  - {}".format(col))
        
        required_columns = ['capacity', 'current_count', 'status']
        all_found = True
        
        print("\nChecking required columns:")
        for col in required_columns:
            if col in columns:
                print("  [OK] {} found".format(col))
            else:
                print("  [MISSING] {} not found".format(col))
                all_found = False
        
        if all_found:
            print("\n[SUCCESS] All required columns are present!")
            
            print("\nTesting data operations...")
            
            test_name = "TestSpot_{}".format(datetime.now().strftime('%Y%m%d%H%M%S'))
            
            try:
                db.execute(text("""
                    INSERT INTO scenic_spots (name, capacity, current_count, status, created_at)
                    VALUES (:name, :capacity, :current_count, :status, :created_at)
                """), {
                    "name": test_name,
                    "capacity": 100,
                    "current_count": 85,
                    "status": "正常开放",
                    "created_at": datetime.now()
                })
                db.commit()
                print("  [OK] Insert test data succeeded")
                
                result = db.execute(text("""
                    SELECT id, name, capacity, current_count, status, 
                           (current_count * 1.0 / capacity) as saturation
                    FROM scenic_spots WHERE name = :name
                """), {"name": test_name})
                
                row = result.fetchone()
                if row:
                    saturation = row[5]
                    print("  [OK] Read test data:")
                    print("       ID: {}".format(row[0]))
                    print("       Name: {}".format(row[1]))
                    print("       Capacity: {}".format(row[2]))
                    print("       Current Count: {}".format(row[3]))
                    print("       Status: {}".format(row[4]))
                    print("       Saturation: {:.1f}%".format(saturation * 100))
                    
                    if saturation >= 0.8:
                        print("       [Diversion Triggered] Saturation >= 80%")
                    else:
                        print("       [No Diversion] Saturation < 80%")
                
                db.execute(text("DELETE FROM scenic_spots WHERE name = :name"), {"name": test_name})
                db.commit()
                print("  [OK] Cleanup test data succeeded")
                
                print("\n" + "=" * 60)
                print("Database verification PASSED!")
                print("=" * 60)
                return True
                
            except Exception as e:
                print("  [ERROR] Data operation failed: {}".format(e))
                import traceback
                traceback.print_exc()
                db.rollback()
                return False
        else:
            print("\n[ERROR] Some required columns are missing!")
            return False
            
    except Exception as e:
        print("\n[ERROR] {}".format(e))
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
