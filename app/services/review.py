import json

from app.db.models import CorrectionItem, CorrectionStatus
from app.models.course_ir import AuditCategory, CourseIR


AUTO_APPLY_THRESHOLD = 0.9


def apply_auto_corrections(db, job, course_ir: CourseIR):
    for item in course_ir.items:
        for corr in item.corrections:
            db_item = (
                db.query(CorrectionItem)
                .filter(CorrectionItem.job_id == job.id, CorrectionItem.original == corr.original)
                .first()
            )
            if not db_item:
                continue
            if corr.confidence >= AUTO_APPLY_THRESHOLD and item.audit_category == AuditCategory.CERTAIN_ERROR:
                db_item.status = CorrectionStatus.AUTO_APPLIED
            else:
                db_item.status = CorrectionStatus.PENDING
    db.commit()


def needs_review(db, job) -> bool:
    pending = (
        db.query(CorrectionItem)
        .filter(CorrectionItem.job_id == job.id, CorrectionItem.status == CorrectionStatus.PENDING)
        .count()
    )
    return pending > 0


def approve_correction(db, correction_id: int, approved: bool):
    item = db.query(CorrectionItem).filter(CorrectionItem.id == correction_id).one()
    item.status = CorrectionStatus.APPROVED if approved else CorrectionStatus.REJECTED
    db.commit()
    return item
