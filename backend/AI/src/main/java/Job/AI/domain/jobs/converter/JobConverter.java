package Job.AI.domain.jobs.converter;

import Job.AI.domain.jobs.dto.JobResponseDTO;

import java.util.List;

public class JobConverter {

    public static JobResponseDTO.TaskCreationDTO toTaskCreationDTO(String taskId) {
        return JobResponseDTO.TaskCreationDTO.builder()
                .taskId(taskId)
                .build();
    }

    public static JobResponseDTO.TaskStatusDTO toTaskStatusDTO(
            String status,
            String message,
            List<JobResponseDTO.JobDataDTO> data
    ) {
        return JobResponseDTO.TaskStatusDTO.builder()
                .status(status)
                .message(message)
                .data(data)
                .build();
    }
}
