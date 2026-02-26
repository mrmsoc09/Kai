# K1 Agent Training & Subagent Systems

**Date**: February 2, 2025
**Status**: ✅ Complete - Training with HiL approval & subagent hierarchy
**Version**: v7.2 Training and Skill Development

---

## Overview

K1 agents can now autonomously request training, develop specialized skills, spawn subagents with inherited knowledge, and teach their subagents. All training requires Human-in-the-Loop (HiL) approval, ensuring safety and control while enabling autonomous learning.

### Key Features

- **Autonomous Training Requests**: Agents identify skill gaps and request training autonomously
- **Human-in-the-Loop Approval**: All training requests require human approval before execution
- **Skill Profiling System**: Detailed skill tracking with proficiency levels and certification
- **Skill Inheritance**: Subagents inherit parent skills at 70% proficiency
- **Knowledge Transfer**: Parents teach subagents with transfer efficiency tracking
- **Training Schedules**: Structured training curriculums with multiple training types
- **Progress Tracking**: Real-time monitoring of training sessions and skill development

---

## Architecture

### Three Major Systems

#### 1. **Skill System**
**File**: `apps/backend/src/core/skill_system.py` (~500 lines)

**Components**:
- `SkillProfile`: Individual skill with proficiency tracking, experience history, certification levels
- `AgentSkillSet`: Complete skill set for an agent with synergy tracking
- `SkillCategory`: 8 skill categories (reconnaissance, validation, analysis, exploitation, reporting, learning, collaboration, planning)
- `ProficiencyLevel`: 5 certification levels (novice, apprentice, journeyman, expert, master)
- `SkillExperience`: Atomic experience record with outcome tracking
- `SkillTransfer`: Knowledge transfer between agents with effectiveness tracking

**Key Metrics**:
- Proficiency (0-1): Current skill level
- Success Rate: Recent success percentage
- Learning Rate: Speed of improvement
- Plateau Level: Natural maximum for this agent
- Certification Level: Formal proficiency designation
- Teaches To Proficiency: Can teach others to this level (if proficient enough)

**Proficiency Certification**:
- NOVICE: 0.0-0.2 proficiency
- APPRENTICE: 0.2-0.4 proficiency
- JOURNEYMAN: 0.4-0.6 proficiency (works independently)
- EXPERT: 0.6-0.8 proficiency (teaches others)
- MASTER: 0.8-1.0 proficiency (world-class)

#### 2. **Agent Training System**
**File**: `apps/backend/src/core/agent_training.py` (~800 lines)

**Components**:
- `TrainingRequest`: Request submitted by agent for human approval
- `TrainingCurriculum`: Structured training plan for skill development
- `TrainingTask`: Single training exercise or challenge
- `TrainingSession`: Active training with progress tracking
- `TrainingSchedule`: Long-term training plan for agent
- `AgentTrainingSystem`: Orchestrates all training with HiL approval workflow

**Training Types**:
- SUPERVISED: Learn from examples
- PRACTICE: Practice on tasks
- MENTORING: Learn from expert agent
- SIMULATION: Simulated scenarios
- SELF_STUDY: Self-directed learning

**Workflow**:
1. Agent autonomously identifies training need
2. Agent requests training (provides justification, confidence, estimated duration)
3. **[HiL APPROVAL]** Human reviews and approves/rejects
4. Upon approval, training session starts automatically
5. Agent completes training tasks with tracking
6. Session completes with proficiency gain recorded
7. Agent skill updated with new proficiency

#### 3. **Subagent Architecture**
**File**: `apps/backend/src/core/autonomous_agent_system.py` (enhanced)

**Enhancements to AutonomousAgent**:
- `parent_agent_id`: Link to parent agent
- `subagents`: Dictionary of spawned child agents
- `can_spawn_subagents`: Permission control
- `max_subagents`: Maximum child agents (default 5)
- `skill_set`: Integrated AgentSkillSet for detailed skill tracking
- `training_enabled`: Can participate in training
- `mentoring_capabilities`: Can teach subagents

**Subagent Features**:
- Spawn with reduced autonomy level (less autonomous than parent)
- Inherit parent skills at 70% proficiency
- Register as peer with parent in collaboration network
- Cannot spawn their own subagents (prevents runaway spawning)
- Can request training autonomously
- Parent can teach skills directly

---

## API Endpoints

### Training Requests (Autonomous)

#### POST `/api/agents/{agent_id}/request-training`
**Description**: Agent autonomously requests training
**Parameters**:
- `skill_name`: Skill to develop
- `target_proficiency`: Desired proficiency level (0-1)
- `reason`: Why agent wants this skill
- `confidence`: Agent's confidence in success (0-1)
- `estimated_duration`: Estimated time in minutes (auto-calculated if omitted)

**Response**:
```json
{
  "request_id": "train_req_abc123",
  "status": "pending_approval",
  "agent_id": "agent_xyz",
  "skill_name": "reconnaissance",
  "current_proficiency": 0.45,
  "target_proficiency": 0.75,
  "estimated_duration": 240,
  "requested_at": "2025-02-02T15:50:12Z",
  "message": "Training request submitted. Awaiting human approval."
}
```

### HiL Approval Endpoints

#### GET `/api/agents/training/pending-approvals`
**Description**: Get all training requests awaiting approval
**Response**:
```json
{
  "pending_count": 3,
  "requests": [
    {
      "request_id": "train_req_abc123",
      "agent_id": "agent_xyz",
      "skill_name": "reconnaissance",
      "current_proficiency": 0.45,
      "target_proficiency": 0.75,
      "status": "pending_approval",
      "reason": "Need better OSINT skills for target discovery"
    }
  ]
}
```

#### POST `/api/agents/training/{request_id}/approve`
**Description**: Human approves training request
**Parameters**:
- `approved_by`: Human approver name
- `notes`: Optional approval notes

**Response**:
```json
{
  "request_id": "train_req_abc123",
  "status": "approved",
  "approved_by": "security_team",
  "training_session_id": "sess_def456",
  "message": "Training approved and session started"
}
```

#### POST `/api/agents/training/{request_id}/reject`
**Description**: Human rejects training request
**Parameters**:
- `rejected_by`: Human rejector name
- `reason`: Rejection reason

**Response**:
```json
{
  "request_id": "train_req_abc123",
  "status": "rejected",
  "rejected_by": "security_team",
  "rejection_reason": "Skill not required for current mission",
  "message": "Training request rejected"
}
```

### Training Sessions

#### GET `/api/agents/training/sessions/active`
**Description**: Get all active training sessions
**Response**:
```json
{
  "active_sessions": 2,
  "sessions": [
    {
      "session_id": "sess_def456",
      "agent_id": "agent_xyz",
      "skill_name": "reconnaissance",
      "progress": 0.35,
      "tasks_completed": 7,
      "status": "in_progress",
      "elapsed_time": 45,
      "time_remaining": 195,
      "efficiency_score": 0.78
    }
  ]
}
```

#### POST `/api/agents/training/sessions/{session_id}/record-task`
**Description**: Record completion of training task
**Parameters**:
- `task_id`: Task identifier
- `success`: Was task successful
- `quality_score`: Quality of execution (0-1)
- `proficiency_gain`: Skill improvement from task (0-1)
- `feedback`: Optional feedback

**Response**:
```json
{
  "session_id": "sess_def456",
  "tasks_completed": 8,
  "overall_progress": 0.40,
  "new_proficiency": 0.49
}
```

#### POST `/api/agents/training/sessions/{session_id}/complete`
**Description**: Complete training session
**Parameters**:
- `final_proficiency`: Final proficiency level achieved
- `quality_score`: Session quality (0-1)

**Response**:
```json
{
  "session_id": "sess_def456",
  "status": "completed",
  "final_proficiency": 0.75,
  "completion_quality": 0.92,
  "efficiency_score": 0.87,
  "elapsed_time": 240,
  "message": "Training session completed successfully"
}
```

### Skill Management

#### GET `/api/agents/{agent_id}/skills`
**Description**: Get all skills for agent
**Response**:
```json
{
  "agent_id": "agent_xyz",
  "average_proficiency": 0.65,
  "specialization_score": 0.42,
  "learning_velocity": 0.045,
  "total_skills": 5,
  "primary_skills": ["reconnaissance", "validation"],
  "proficient_skills": ["reconnaissance", "validation", "analysis"],
  "expert_skills": ["reconnaissance"],
  "master_skills": [],
  "skills": {
    "reconnaissance": {
      "skill_name": "reconnaissance",
      "proficiency": 0.85,
      "proficiency_description": "Expert (85.0%)",
      "total_experience": 142,
      "success_rate": 0.87,
      "certification_level": "expert",
      "certified_at": "2025-01-15T10:30:00Z",
      "learning_rate": 0.045,
      "can_teach": true
    }
  }
}
```

#### GET `/api/agents/{agent_id}/skills/{skill_name}`
**Description**: Get specific skill profile
**Response**:
```json
{
  "skill_name": "reconnaissance",
  "category": "reconnaissance",
  "proficiency": 0.85,
  "proficiency_description": "Expert (85.0%)",
  "total_experience": 142,
  "success_rate": 0.87,
  "certification_level": "expert",
  "certified_at": "2025-01-15T10:30:00Z",
  "learning_rate": 0.045,
  "can_teach": true,
  "teaches_to_proficiency": 0.75
}
```

#### POST `/api/agents/{agent_id}/skills/{skill_name}/record-experience`
**Description**: Record skill experience for learning
**Parameters**:
- `success`: Was experience successful
- `quality_score`: Quality (0-1)
- `confidence`: Agent's confidence (0-1)
- `context`: Optional context information

**Response**:
```json
{
  "agent_id": "agent_xyz",
  "skill_name": "reconnaissance",
  "recorded": true,
  "new_proficiency": 0.86,
  "success_rate": 0.88
}
```

### Subagent Management

#### POST `/api/agents/{agent_id}/spawn-subagent`
**Description**: Parent agent spawns a subagent
**Parameters**:
- `name`: Subagent name
- `objective`: Agent objective (DISCOVER_VULNERABILITIES, etc.)
- `inherit_skills`: Inherit parent skills (default: true)

**Response**:
```json
{
  "parent_id": "agent_xyz",
  "subagent_id": "agent_sub1",
  "name": "reconnaissance_specialist",
  "objective": "discover_vulnerabilities",
  "autonomy_level": 2,
  "inherits_skills": true,
  "message": "Subagent 'reconnaissance_specialist' spawned successfully"
}
```

#### GET `/api/agents/{agent_id}/subagents`
**Description**: Get subagent hierarchy
**Response**:
```json
{
  "agent_id": "agent_xyz",
  "parent_id": null,
  "subagent_count": 2,
  "max_subagents": 5,
  "subagents": {
    "agent_sub1": {
      "name": "reconnaissance_specialist",
      "objective": "discover_vulnerabilities",
      "autonomy_level": 2,
      "status": "idle"
    },
    "agent_sub2": {
      "name": "validator_specialist",
      "objective": "validate_findings",
      "autonomy_level": 2,
      "status": "executing"
    }
  }
}
```

#### POST `/api/agents/{agent_id}/teach-subagent/{subagent_id}`
**Description**: Parent teaches skill to subagent
**Parameters**:
- `skill_name`: Skill to teach
- `target_proficiency`: Target proficiency for student
- `session_duration`: Teaching session duration in minutes

**Response**:
```json
{
  "teacher_id": "agent_xyz",
  "student_id": "agent_sub1",
  "skill_name": "reconnaissance",
  "transfer_efficiency": 0.65,
  "proficiency_gain": 0.12,
  "new_student_proficiency": 0.72,
  "teaching_successful": true
}
```

### Training Analytics

#### GET `/api/agents/{agent_id}/training-history`
**Description**: Get agent's training history
**Response**:
```json
{
  "agent_id": "agent_xyz",
  "statistics": {
    "total_sessions": 5,
    "total_training_hours": 18.5,
    "average_completion_quality": 0.88,
    "average_efficiency_score": 0.81,
    "skills_trained": ["reconnaissance", "validation", "analysis"],
    "last_training": "2025-02-01T14:20:00Z"
  },
  "sessions": [...]
}
```

#### POST `/api/agents/{agent_id}/identify-training-needs`
**Description**: Autonomously identify agent's training needs
**Response**:
```json
{
  "agent_id": "agent_xyz",
  "current_skills": {
    "reconnaissance": 0.85,
    "validation": 0.65,
    "analysis": 0.55
  },
  "recommendations": [
    {
      "skill_name": "analysis",
      "gap_size": 0.25,
      "priority": "high",
      "estimated_hours": 16,
      "recommendation": "Developing analysis skills would significantly improve vulnerability classification"
    }
  ]
}
```

#### POST `/api/agents/{agent_id}/generate-training-plan`
**Description**: Generate personalized training plan
**Parameters**:
- `skill_name`: Skill to develop
- `current_proficiency`: Current level
- `target_proficiency`: Target level

**Response**:
```json
{
  "agent_id": "agent_xyz",
  "skill_name": "analysis",
  "training_plan": {
    "stages": [
      {
        "stage": 1,
        "name": "Fundamentals",
        "duration": 120,
        "milestones": ["Understand common vulnerability patterns"],
        "resources": ["CVE database", "OWASP Top 10"]
      },
      {
        "stage": 2,
        "name": "Advanced Techniques",
        "duration": 180,
        "milestones": ["Perform full system analysis"]
      }
    ],
    "total_estimated_duration": 300
  }
}
```

---

## Usage Workflow

### Scenario: Agent Identifies Training Need

**Step 1: Agent Autonomously Requests Training**
```bash
curl -X POST http://localhost:8000/api/agents/agent_xyz/request-training \
  -H "Content-Type: application/json" \
  -d '{
    "skill_name": "analysis",
    "target_proficiency": 0.75,
    "reason": "Found that many findings are rejected due to poor analysis. Need to improve analytical skills.",
    "confidence": 0.8,
    "estimated_duration": 240
  }'
```

**Response**: Training request submitted and awaiting approval

**Step 2: Human Reviews Pending Approvals**
```bash
curl http://localhost:8000/api/agents/training/pending-approvals
```

**Step 3: Human Approves Training**
```bash
curl -X POST http://localhost:8000/api/agents/training/train_req_abc123/approve \
  -H "Content-Type: application/json" \
  -d '{
    "approved_by": "security_team",
    "notes": "Approved. Analysis skills critical for finding quality."
  }'
```

**Response**: Training session created and started automatically

**Step 4: Monitor Training Progress**
```bash
curl http://localhost:8000/api/agents/training/sessions/sess_def456
```

**Step 5: Record Task Completion (called by agent during training)**
```bash
curl -X POST http://localhost:8000/api/agents/training/sessions/sess_def456/record-task \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task_001",
    "success": true,
    "quality_score": 0.92,
    "proficiency_gain": 0.08,
    "feedback": "Excellent analysis of XSS vulnerability patterns"
  }'
```

**Step 6: Complete Training Session**
```bash
curl -X POST http://localhost:8000/api/agents/training/sessions/sess_def456/complete \
  -H "Content-Type: application/json" \
  -d '{
    "final_proficiency": 0.75,
    "quality_score": 0.90
  }'
```

### Scenario: Parent Agent Spawns Subagent

**Step 1: Parent Spawns Subagent**
```bash
curl -X POST http://localhost:8000/api/agents/agent_xyz/spawn-subagent \
  -H "Content-Type: application/json" \
  -d '{
    "name": "validation_specialist",
    "objective": "validate_findings",
    "inherit_skills": true
  }'
```

**Response**: Subagent created with inherited skills

**Step 2: Parent Teaches Skill to Subagent**
```bash
curl -X POST http://localhost:8000/api/agents/agent_xyz/teach-subagent/agent_sub1 \
  -H "Content-Type: application/json" \
  -d '{
    "skill_name": "validation",
    "target_proficiency": 0.80,
    "session_duration": 120
  }'
```

**Response**: Knowledge transferred with efficiency metrics

**Step 3: Subagent Can Autonomously Request Training**
```bash
curl -X POST http://localhost:8000/api/agents/agent_sub1/request-training \
  -H "Content-Type: application/json" \
  -d '{
    "skill_name": "analysis",
    "target_proficiency": 0.70,
    "reason": "Want to improve analysis to support parent agent",
    "confidence": 0.7
  }'
```

---

## Key Features

### Autonomy + Control

| Feature | Autonomous | Human Approval |
|---------|-----------|-----------------|
| Identify training needs | ✓ | - |
| Request training | ✓ | ✓ (REQUIRED) |
| Execute approved training | ✓ | - |
| Record experiences | ✓ | - |
| Spawn subagents | ✓ | - |
| Teach subagents | ✓ | - |
| Complete training | ✓ | - |

### Skill Development

- **Learning from Experience**: Each task/action records experience with success/quality metrics
- **Proficiency Progression**: Proficiency increases based on successful experiences
- **Certification Levels**: Automatic certification as proficiency reaches thresholds
- **Teaching Capability**: Expert+ agents can teach subagents
- **Skill Synergies**: Skills can have synergy bonuses when used together

### Safety & Oversight

- **HiL Approval**: All training requires human approval before execution
- **Request Justification**: Agents must explain why they need training
- **Confidence Scoring**: Agents indicate confidence in success
- **Duration Estimation**: Agents estimate required training time
- **Progress Transparency**: All training sessions fully logged and trackable
- **Rejection Option**: Humans can reject training requests with explanation

---

## Default Curriculums

System creates default curriculums for core skills:

1. **Reconnaissance**: Information gathering and enumeration
2. **Validation**: Finding verification and confirmation
3. **Analysis**: System analysis and vulnerability mapping
4. **Exploitation**: Attack execution and payload delivery
5. **Reporting**: Report generation and documentation

Each curriculum:
- Target proficiency: 0.8 (Expert level)
- Training type: PRACTICE (hands-on learning)
- Can be customized per agent

---

## Performance Metrics

### Agent Training Metrics
- Total training hours
- Average session completion quality
- Average efficiency score
- Skills trained
- Last training date

### Skill Metrics
- Current proficiency (0-1)
- Certification level
- Success rate
- Learning rate
- Days since last use
- Teaching capability

### Subagent Metrics
- Number of subagents
- Skills inherited vs. trained
- Teaching effectiveness
- Knowledge transfer efficiency

---

## Security Considerations

### HiL Approval Workflow

1. **Request Submission**: Agent requests training with justification
2. **Review Period**: Human reviews request details
3. **Approval Decision**: Human approves/rejects with reasons
4. **Training Execution**: Approved training executes autonomously
5. **Completion Tracking**: All training fully logged

### Autonomy Controls

- Subagents have reduced autonomy (spawner - 1 level)
- Subagents cannot spawn further subagents
- Training is optional (agent can proceed without)
- All skill changes auditable
- Training history preserved

### Skill Transfer Safety

- Parent must have required proficiency to teach
- Transfer efficiency caps prevent unrealistic knowledge jumps
- Student proficiency increases gradually
- All transfers tracked with effectiveness metrics

---

## Integration Points

### With Autonomous Agents
- Agents track skills in AgentSkillSet
- Experience recording feeds into skill progression
- Training requests feed back into orchestrator

### With LLM Providers
- Training system uses LLM to:
  - Identify training needs
  - Generate training plans
  - Create appropriate tasks
  - Provide feedback

### With MCP Servers
- Training tasks executed via MCP tools
- Tool execution counted as skill experience
- Success/failure feeds back to skill system

### With Agent Zero
- Training requests appear as capabilities
- Subagent spawning increases team capacity
- Skill progression improves mission success

---

## Future Enhancements

### Planned Features
- **Peer Learning**: Agents teach each other in collaborative sessions
- **Skill Prerequisites**: Enforce skill dependencies (can't learn advanced before basics)
- **Performance Plateaus**: Customize learning curve per skill/agent
- **Specialty Certification**: Official certifications for critical skills
- **Knowledge Persistence**: Training retained across sessions
- **Transfer Learning**: Knowledge from one skill aids others
- **Emergent Teaching**: Experienced agents become teachers autonomously

### Advanced Scenarios
- Multi-agent mentoring circles (circular teaching)
- Skill-based team composition for complex tasks
- Competitive skill development (agents compete to master skills)
- Collaborative learning projects
- Skill degradation when unused (need practice)

---

## Configuration

### Environment Variables
```bash
K1_MAX_SUBAGENTS=5
K1_SKILL_PLATEAU_DEFAULT=0.95
K1_TRAINING_ENABLED=true
K1_HIL_APPROVAL_REQUIRED=true
```

### Training Defaults
```python
MAX_SUBAGENTS = 5
SUBAGENT_AUTONOMY_REDUCTION = 1  # Subagent autonomy = parent - 1
SKILL_INHERITANCE_FACTOR = 0.7  # Subagents inherit at 70%
```

---

## Files Modified/Created

**Created**:
- `apps/backend/src/core/skill_system.py` (500 lines) - Comprehensive skill system
- `apps/backend/src/core/agent_training.py` (800 lines) - Training orchestration with HiL
- `apps/backend/src/routers/agent_training.py` (600 lines) - Training API endpoints

**Modified**:
- `apps/backend/src/core/autonomous_agent_system.py` (+200 lines) - Skill integration and subagent spawn
- `apps/backend/src/main.py` (+50 lines) - Training system initialization

**Total New Code**: 2,150 lines

---

## Success Criteria (Met)

✅ Skill system with proficiency tracking
✅ Autonomous training requests by agents
✅ Human-in-the-Loop approval workflow
✅ Training sessions with progress tracking
✅ Subagent spawning with skill inheritance
✅ Parent-child knowledge transfer
✅ Skill experience recording and learning
✅ Comprehensive training analytics
✅ Integration with LLM providers
✅ Full API exposure
✅ Production-ready implementation

---

**Status**: Complete and ready for production deployment

The agent training and subagent systems enable K1 to develop increasingly sophisticated autonomous teams with sophisticated skill development while maintaining human oversight through the HiL approval workflow.
