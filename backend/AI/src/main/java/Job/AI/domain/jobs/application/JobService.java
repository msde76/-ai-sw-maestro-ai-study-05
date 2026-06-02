package Job.AI.domain.jobs.application;

import Job.AI.domain.jobs.dto.JobRequestDTO;
import Job.AI.domain.jobs.dto.JobResponseDTO;

public interface JobService {
    // 작업 생성 (비동기 처리 트리거)
    JobResponseDTO.TaskCreationDTO setTask(JobRequestDTO.TaskInfoDTO taskInfo);

    // 작업 상태 조회 (Polling)
    JobResponseDTO.TaskStatusDTO getTaskStatus(String taskId);
}