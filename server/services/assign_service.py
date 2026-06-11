#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
线索分配服务
- Round-Robin循环分配：团队内员工依次分配
- 分配后触发钉钉推送
- 主播名自动填充
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def get_next_employee(team_id: int, db) -> Optional[int]:
    """获取团队内下一个应分配的员工ID
    - 单人模式(single): 始终返回指定员工
    - 轮流模式(round_robin): Round-Robin 循环分配
    """
    from models import RecruitEmployee, ClueAssignment, RecruitTeam

    team = db.query(RecruitTeam).get(team_id)
    if not team:
        return None

    # 单人分配模式
    if team.assign_mode == 'single' and team.assignee_id:
        # 验证指定员工是否活跃
        emp = db.query(RecruitEmployee).filter(
            RecruitEmployee.id == team.assignee_id,
            RecruitEmployee.is_active == True,
        ).first()
        if emp:
            return emp.id

    # 获取团队内所有活跃员工，按sort_order排序
    employees = db.query(RecruitEmployee).filter(
        RecruitEmployee.team_id == team_id,
        RecruitEmployee.is_active == True,
    ).order_by(RecruitEmployee.sort_order, RecruitEmployee.id).all()

    if not employees:
        return None

    # 查找该团队最近一次分配记录
    last_assignment = db.query(ClueAssignment).filter(
        ClueAssignment.team_id == team_id,
    ).order_by(ClueAssignment.assigned_at.desc()).first()

    if not last_assignment:
        # 从第一个员工开始
        return employees[0].id

    # 找到上次分配的员工在列表中的位置，取下一个
    emp_ids = [e.id for e in employees]
    try:
        last_idx = emp_ids.index(last_assignment.employee_id)
        next_idx = (last_idx + 1) % len(emp_ids)
        return emp_ids[next_idx]
    except ValueError:
        # 上次分配的员工已不在列表中，从头开始
        return employees[0].id


def fill_anchor_names(clue, db):
    """填充线索的主播名（根据anchor_id或create_time匹配排班）"""
    from models import Anchor, SessionAnchor, Session, ScheduleBinding, ScheduleSlot

    if clue.anchor_names:
        return  # 已有主播名

    # 优先用anchor_id
    if clue.anchor_id:
        anchor = db.query(Anchor).get(clue.anchor_id)
        if anchor:
            clue.anchor_names = anchor.name
            return

    # 通过create_time匹配排班
    if not clue.create_time_detail:
        return

    try:
        clue_dt = datetime.strptime(clue.create_time_detail[:16], "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return

    clue_date = clue.create_time_detail[:10]
    clue_minutes = clue_dt.hour * 60 + clue_dt.minute

    # 查找当天的排班绑定
    binding = db.query(ScheduleBinding).filter(ScheduleBinding.date == clue_date).first()
    if not binding:
        return

    # 查找匹配的时段
    slots = db.query(ScheduleSlot).filter(ScheduleSlot.plan_id == binding.plan_id).all()
    anchor_mapping = {}
    if binding.anchor_mapping:
        import json
        try:
            anchor_mapping = json.loads(binding.anchor_mapping)
        except Exception:
            pass

    for slot in slots:
        # 解析时段
        time_parts = slot.time_slot.split("-")
        if len(time_parts) != 2:
            continue
        try:
            start_min = _parse_time_minutes(time_parts[0].strip())
            end_min = _parse_time_minutes(time_parts[1].strip())
        except Exception:
            continue

        if start_min <= clue_minutes < end_min:
            # 找到匹配时段，查找主播
            anchor_ids = []
            if str(slot.id) in anchor_mapping:
                mapped = anchor_mapping[str(slot.id)]
                if isinstance(mapped, list):
                    anchor_ids = [int(a) for a in mapped if a]
                elif isinstance(mapped, int):
                    anchor_ids = [mapped]

            if anchor_ids:
                anchors = db.query(Anchor).filter(Anchor.id.in_(anchor_ids)).all()
                clue.anchor_names = ",".join([a.name for a in anchors])
            return


def _parse_time_minutes(time_str: str) -> int:
    """解析时间字符串为分钟数，支持跨天（如25:00）"""
    parts = time_str.replace("：", ":").split(":")
    if len(parts) == 2:
        h, m = int(parts[0]), int(parts[1])
        return h * 60 + m
    return 0


def assign_new_clues(db, today_only=True, time_range_days=None):
    """为未分配的新线索执行分配
    Args:
        today_only: 是否只分配当天线索（默认True），避免历史线索被意外推送
        time_range_days: 推送时间区间（天），如为3则只分配3天内的线索。优先于today_only
    """
    from models import ApiClue, ClueAssignment, RecruitTeam

    # 查找所有未分配的线索
    query = db.query(ApiClue).filter(
        ~ApiClue.id.in_(db.query(ClueAssignment.clue_id))
    )

    # 时间区间过滤
    if time_range_days is not None:
        # 按配置的时间区间过滤
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=time_range_days)).strftime("%Y-%m-%d")
        query = query.filter(ApiClue.create_time_detail >= cutoff)
    elif today_only:
        # 只分配当天线索，避免历史线索被意外推送
        today_str = datetime.now().strftime("%Y-%m-%d")
        query = query.filter(ApiClue.create_time_detail >= today_str)

    unassigned = query.order_by(ApiClue.create_time_detail).all()

    if not unassigned:
        return 0

    # 获取所有启用了推送的活跃团队
    teams = db.query(RecruitTeam).filter(
        RecruitTeam.is_active == True,
        RecruitTeam.push_enabled == True,
    ).all()
    if not teams:
        logger.info("无启用推送的活跃团队，跳过分配")
        return 0

    # 排序：有钉钉webhook的团队优先
    teams_with_webhook = [t for t in teams if t.dingtalk_webhook]
    teams_without_webhook = [t for t in teams if not t.dingtalk_webhook]
    teams = teams_with_webhook + teams_without_webhook

    assigned_count = 0
    # 简单策略：所有团队轮流分配（如只有1个团队则全部归该团队）
    team_idx = 0

    for clue in unassigned:
        # 填充主播名
        fill_anchor_names(clue, db)

        # 选择团队
        team = teams[team_idx % len(teams)]
        team_idx += 1

        # 获取下一个员工
        employee_id = get_next_employee(team.id, db)
        if not employee_id:
            continue

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        assignment = ClueAssignment(
            clue_id=clue.id,
            team_id=team.id,
            employee_id=employee_id,
            assigned_at=now,
            status="unclaimed",
        )
        db.add(assignment)
        assigned_count += 1

        # 触发钉钉推送
        try:
            from services.dingtalk_service import send_clue_notification
            send_clue_notification(team, employee_id, clue, db)
        except Exception as e:
            logger.error(f"钉钉推送失败: {e}")

    db.commit()
    logger.info(f"线索分配完成: 共分配{assigned_count}条")
    return assigned_count


def assign_to_employee(clue_id: int, team_id: int, employee_id: int, db) -> Optional[object]:
    """
    手动指定员工分配线索
    - 验证clue_id是否存在且未分配
    - 验证team_id和employee_id是否存在且活跃
    - 创建ClueAssignment记录
    - 触发钉钉推送
    - 返回分配记录对象
    """
    from models import ApiClue, ClueAssignment, RecruitTeam, RecruitEmployee

    # 1. 验证线索是否存在
    clue = db.query(ApiClue).get(clue_id)
    if not clue:
        logger.error(f"线索不存在: clue_id={clue_id}")
        return None

    # 2. 验证线索是否已分配
    existing = db.query(ClueAssignment).filter(ClueAssignment.clue_id == clue_id).first()
    if existing:
        logger.error(f"线索已分配: clue_id={clue_id}, assignment_id={existing.id}")
        return None

    # 3. 验证团队是否存在且活跃
    team = db.query(RecruitTeam).filter(
        RecruitTeam.id == team_id,
        RecruitTeam.is_active == True
    ).first()
    if not team:
        logger.error(f"团队不存在或未激活: team_id={team_id}")
        return None

    # 4. 验证员工是否存在且活跃
    employee = db.query(RecruitEmployee).filter(
        RecruitEmployee.id == employee_id,
        RecruitEmployee.team_id == team_id,
        RecruitEmployee.is_active == True
    ).first()
    if not employee:
        logger.error(f"员工不存在或未激活: employee_id={employee_id}")
        return None

    # 5. 创建分配记录
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    assignment = ClueAssignment(
        clue_id=clue_id,
        team_id=team_id,
        employee_id=employee_id,
        assigned_at=now,
        status="unclaimed",
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    # 6. 触发钉钉推送
    try:
        from services.dingtalk_service import send_clue_notification
        send_clue_notification(team, employee_id, clue, db)
    except Exception as e:
        logger.error(f"钉钉推送失败: {e}")

    logger.info(f"手动分配完成: clue_id={clue_id}, employee_id={employee_id}")
    return assignment
