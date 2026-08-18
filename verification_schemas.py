# verification_schemas.py

TB_GENERATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verification_plan", "testbench_sv"],
    "properties": {
        "verification_plan": {
            "type": "string",
            "minLength": 10
        },
        "testbench_sv": {
            "type": "string",
            "minLength": 10
        }
    }
}

REPAIR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action", "diagnosis", "bug_class", "repair_summary"],
    "properties": {
        "action": {
            "type": "string",
            "enum": ["REPAIR_RTL", "REPAIR_TB", "BLOCK", "REQUEST_MORE_EVIDENCE"]
        },
        "diagnosis": {
            "type": "string",
            "minLength": 5
        },
        "bug_class": {
            "type": "string",
            "enum": ["syntax_error", "width_mismatch", "logical_error", "timing_error", "testbench_error", "specification_conflict", "other"]
        },
        "repair_summary": {
            "type": "string",
            "minLength": 5
        },
        "repaired_rtl": {
            "type": "string",
            "description": "Provide ONLY if action is REPAIR_RTL."
        },
        "repaired_testbench_sv": {
            "type": "string",
            "description": "Provide ONLY if action is REPAIR_TB."
        }
    }
}