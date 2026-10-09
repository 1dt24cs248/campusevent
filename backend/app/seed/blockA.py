from app.models.campus import Block, Floor, Room

def seed_block_a(db):
    block = db.query(Block).filter(Block.id == "block_A").first()
    if not block:
        block = Block(id="block_A", code="A", name="Block A", is_active=True, is_pilot=True)
        db.add(block)
        db.commit()
    
    floors_data = [
        {"id": "floor_A_basement", "level": -1, "name": "Basement"},
        {"id": "floor_A_ground", "level": 0, "name": "Ground Floor"},
        {"id": "floor_A_1", "level": 1, "name": "1st Floor"},
        {"id": "floor_A_2", "level": 2, "name": "2nd Floor"},
        {"id": "floor_A_3", "level": 3, "name": "3rd Floor"},
        {"id": "floor_A_4", "level": 4, "name": "4th Floor"},
        {"id": "floor_A_5", "level": 5, "name": "5th Floor"},
    ]
    
    for f in floors_data:
        existing = db.query(Floor).filter(Floor.id == f["id"]).first()
        if not existing:
            db.add(Floor(id=f["id"], block_id="block_A", level=f["level"], name=f["name"]))
    db.commit()

    rooms_data = [
        # BASEMENT (-1)
        {"id": "room_SH-01", "floor_id": "floor_A_basement", "code": "SH-01", "display_name": "Seminar Hall 1", "type": "SEMINAR_HALL", "cap": 100, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR", "PA_SYSTEM"]},
        {"id": "room_SH-02", "floor_id": "floor_A_basement", "code": "SH-02", "display_name": "Seminar Hall 2", "type": "SEMINAR_HALL", "cap": 80, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR", "PA_SYSTEM"]},
        {"id": "room_B03", "floor_id": "floor_A_basement", "code": "B03", "display_name": "Classroom B03", "type": "CLASSROOM", "cap": 60, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_B04", "floor_id": "floor_A_basement", "code": "B04", "display_name": "Classroom B04", "type": "CLASSROOM", "cap": 55, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_B05", "floor_id": "floor_A_basement", "code": "B05", "display_name": "Classroom B05", "type": "CLASSROOM", "cap": 70, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_aiml_lab", "floor_id": "floor_A_basement", "code": "AIML Lab", "display_name": "AIML Lab", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "AIML", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_phy_lab", "floor_id": "floor_A_basement", "code": "Physics Lab", "display_name": "Physics Lab", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "PHYSICS", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_chem_lab", "floor_id": "floor_A_basement", "code": "Chemistry Lab", "display_name": "Chemistry Lab", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "CHEMISTRY", "fac": ["LAB_EQUIPMENT"]},
        
        # GROUND FLOOR (0)
        {"id": "room_prin_off", "floor_id": "floor_A_ground", "code": "Principal Office", "display_name": "Principal Office", "type": "OFFICE", "cap": None, "prov": None, "alloc": False, "res": False, "fac": []},
        {"id": "room_adm_block", "floor_id": "floor_A_ground", "code": "Admission Block", "display_name": "Admission Block", "type": "OFFICE", "cap": None, "prov": None, "alloc": False, "res": False, "fac": []},
        {"id": "room_enq_off", "floor_id": "floor_A_ground", "code": "Enquiry Office", "display_name": "Enquiry Office", "type": "OFFICE", "cap": None, "prov": None, "alloc": False, "res": False, "fac": []},
        {"id": "room_meet_hall", "floor_id": "floor_A_ground", "code": "Meeting Hall", "display_name": "Meeting Hall", "type": "MEETING_HALL", "cap": None, "prov": None, "alloc": False, "res": True, "fac": []},
        
        # 1ST FLOOR (1)
        {"id": "room_A101", "floor_id": "floor_A_1", "code": "A101", "display_name": "Classroom A101", "type": "CLASSROOM", "cap": 60, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A102", "floor_id": "floor_A_1", "code": "A102", "display_name": "Classroom A102", "type": "CLASSROOM", "cap": 65, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A103", "floor_id": "floor_A_1", "code": "A103", "display_name": "Classroom A103", "type": "CLASSROOM", "cap": 50, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A104", "floor_id": "floor_A_1", "code": "A104", "display_name": "Classroom A104", "type": "CLASSROOM", "cap": 55, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A105", "floor_id": "floor_A_1", "code": "A105", "display_name": "Classroom A105", "type": "CLASSROOM", "cap": 70, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A106", "floor_id": "floor_A_1", "code": "A106", "display_name": "Classroom A106", "type": "CLASSROOM", "cap": 60, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A107", "floor_id": "floor_A_1", "code": "A107", "display_name": "Classroom A107", "type": "CLASSROOM", "cap": 65, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A108", "floor_id": "floor_A_1", "code": "A108", "display_name": "Classroom A108", "type": "CLASSROOM", "cap": 55, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_cse_lab_1", "floor_id": "floor_A_1", "code": "CSE Lab 1", "display_name": "CSE Lab 1", "type": "LAB", "cap": 35, "prov": "PROVIDED", "alloc": True, "res": False, "lab_kind": "CSE", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_cse_lab_2", "floor_id": "floor_A_1", "code": "CSE Lab 2", "display_name": "CSE Lab 2", "type": "LAB", "cap": 35, "prov": "PROVIDED", "alloc": True, "res": False, "lab_kind": "CSE", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_A1_SPARE", "floor_id": "floor_A_1", "code": "A1-SPARE", "display_name": "Spare A1", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},

        # 2ND FLOOR (2)
        {"id": "room_A201", "floor_id": "floor_A_2", "code": "A201", "display_name": "Classroom A201", "type": "CLASSROOM", "cap": 65, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A202", "floor_id": "floor_A_2", "code": "A202", "display_name": "Classroom A202", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A203", "floor_id": "floor_A_2", "code": "A203", "display_name": "Classroom A203", "type": "CLASSROOM", "cap": 70, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A204", "floor_id": "floor_A_2", "code": "A204", "display_name": "Classroom A204", "type": "CLASSROOM", "cap": 62, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A205", "floor_id": "floor_A_2", "code": "A205", "display_name": "Classroom A205", "type": "CLASSROOM", "cap": 66, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A206", "floor_id": "floor_A_2", "code": "A206", "display_name": "Classroom A206", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A207", "floor_id": "floor_A_2", "code": "A207", "display_name": "Classroom A207", "type": "CLASSROOM", "cap": 68, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A208", "floor_id": "floor_A_2", "code": "A208", "display_name": "Classroom A208", "type": "CLASSROOM", "cap": 64, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_ise_lab_1", "floor_id": "floor_A_2", "code": "ISE Lab 1", "display_name": "ISE Lab 1", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "ISE", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_ise_lab_2", "floor_id": "floor_A_2", "code": "ISE Lab 2", "display_name": "ISE Lab 2", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "ISE", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_A2_SPARE", "floor_id": "floor_A_2", "code": "A2-SPARE", "display_name": "Spare A2", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},

        # 3RD FLOOR (3)
        {"id": "room_A301", "floor_id": "floor_A_3", "code": "A301", "display_name": "Classroom A301", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A302", "floor_id": "floor_A_3", "code": "A302", "display_name": "Classroom A302", "type": "CLASSROOM", "cap": 64, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A303", "floor_id": "floor_A_3", "code": "A303", "display_name": "Classroom A303", "type": "CLASSROOM", "cap": 68, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A304", "floor_id": "floor_A_3", "code": "A304", "display_name": "Classroom A304", "type": "CLASSROOM", "cap": 70, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_cm_lab_1", "floor_id": "floor_A_3", "code": "Civil/Mech Lab 1", "display_name": "Civil/Mech Lab 1", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "MECH_CIVIL", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_cm_lab_2", "floor_id": "floor_A_3", "code": "Civil/Mech Lab 2", "display_name": "Civil/Mech Lab 2", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "MECH_CIVIL", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_cm_lab_3", "floor_id": "floor_A_3", "code": "Civil/Mech Lab 3", "display_name": "Civil/Mech Lab 3", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "MECH_CIVIL", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_A3_SPARE_1", "floor_id": "floor_A_3", "code": "A3-SPARE-1", "display_name": "Spare A3-1", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},
        {"id": "room_A3_SPARE_2", "floor_id": "floor_A_3", "code": "A3-SPARE-2", "display_name": "Spare A3-2", "type": "CLASSROOM", "cap": 64, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},
        {"id": "room_A3_SPARE_3", "floor_id": "floor_A_3", "code": "A3-SPARE-3", "display_name": "Spare A3-3", "type": "CLASSROOM", "cap": 66, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},

        # 4TH FLOOR (4)
        {"id": "room_A401", "floor_id": "floor_A_4", "code": "A401", "display_name": "Classroom A401", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A402", "floor_id": "floor_A_4", "code": "A402", "display_name": "Classroom A402", "type": "CLASSROOM", "cap": 62, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A403", "floor_id": "floor_A_4", "code": "A403", "display_name": "Classroom A403", "type": "CLASSROOM", "cap": 65, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A404", "floor_id": "floor_A_4", "code": "A404", "display_name": "Classroom A404", "type": "CLASSROOM", "cap": 68, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A405", "floor_id": "floor_A_4", "code": "A405", "display_name": "Classroom A405", "type": "CLASSROOM", "cap": 70, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_ds_lab_1", "floor_id": "floor_A_4", "code": "DS Lab 1", "display_name": "DS Lab 1", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "DS", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_ds_lab_2", "floor_id": "floor_A_4", "code": "DS Lab 2", "display_name": "DS Lab 2", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "DS", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_A4_SPARE_1", "floor_id": "floor_A_4", "code": "A4-SPARE-1", "display_name": "Spare A4-1", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},
        {"id": "room_A4_SPARE_2", "floor_id": "floor_A_4", "code": "A4-SPARE-2", "display_name": "Spare A4-2", "type": "CLASSROOM", "cap": 66, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},
        {"id": "room_staff", "floor_id": "floor_A_4", "code": "Staff Room", "display_name": "Staff Room", "type": "STAFF_ROOM", "cap": None, "prov": None, "alloc": False, "res": False, "fac": []},

        # 5TH FLOOR (5)
        {"id": "room_A501", "floor_id": "floor_A_5", "code": "A501", "display_name": "Classroom A501", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A502", "floor_id": "floor_A_5", "code": "A502", "display_name": "Classroom A502", "type": "CLASSROOM", "cap": 64, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A503", "floor_id": "floor_A_5", "code": "A503", "display_name": "Classroom A503", "type": "CLASSROOM", "cap": 66, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A504", "floor_id": "floor_A_5", "code": "A504", "display_name": "Classroom A504", "type": "CLASSROOM", "cap": 70, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A5_SPARE_1", "floor_id": "floor_A_5", "code": "A5-SPARE-1", "display_name": "Spare A5-1", "type": "CLASSROOM", "cap": 62, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},
        {"id": "room_A5_SPARE_2", "floor_id": "floor_A_5", "code": "A5-SPARE-2", "display_name": "Spare A5-2", "type": "CLASSROOM", "cap": 66, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},
        {"id": "room_com_1", "floor_id": "floor_A_5", "code": "Common Room 1", "display_name": "Common Room 1", "type": "COMMON_USE", "cap": None, "prov": None, "alloc": False, "res": False, "fac": []},
        {"id": "room_com_2", "floor_id": "floor_A_5", "code": "Common Room 2", "display_name": "Common Room 2", "type": "COMMON_USE", "cap": None, "prov": None, "alloc": False, "res": False, "fac": []},
    ]

    for r in rooms_data:
        existing = db.query(Room).filter(Room.id == r["id"]).first()
        if not existing:
            room = Room(
                id=r["id"],
                block_id="block_A",
                floor_id=r["floor_id"],
                code=r["code"],
                display_name=r["display_name"],
                resource_type=r["type"],
                capacity=r.get("cap"),
                capacity_provenance=r.get("prov"),
                allocatable_for_classes=r.get("alloc", True),
                reservable_for_events=r.get("res", False),
                lab_kind=r.get("lab_kind"),
                facilities=r.get("fac", []),
                is_spare=r.get("is_spare", False),
                provenance=r.get("prov"),
                accessible=None
            )
            db.add(room)
    
    db.commit()
