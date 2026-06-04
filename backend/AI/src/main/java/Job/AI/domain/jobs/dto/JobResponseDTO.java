package Job.AI.domain.jobs.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

public class JobResponseDTO {

    // 1. POST /tasks 요청 시 즉시 반환되는 DTO
    @Builder
    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TaskCreationDTO {
        private String taskId;
    }

    // 2. GET /tasks/{taskId} 요청 시 반환되는 상태 조회 DTO
    @Builder
    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TaskStatusDTO {
        private String status; // PROCESSING, COMPLETED, EMPTY, ERROR
        private String message;
        private List<JobDataDTO> data;
    }

    @Builder
    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    public static class JobDataDTO {
        private String jobId;
        private String companyName;
        private String jobTitle;
        private String jobIntroduction;
        private Double suitabilityScore;
        private String compensation;
        private String deadline;
        private String originalLink;
        private AnalysisDTO analysis;
    }

    @Builder
    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    public static class AnalysisDTO {
        private String matchReason;
        private String missingPoints;
        private String checkpointGuide;
    }
}