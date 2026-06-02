package Job.AI.domain.jobs.dto;

import lombok.Getter;
import java.util.List;

public class JobRequestDTO {

    @Getter
    public static class TaskInfoDTO {
        private String coverLetter;
        private PreferencesDTO preferences;
    }

    @Getter
    public static class PreferencesDTO {
        private String jobRole;
        private String experienceLevel;
        private List<String> techStack;
        private String region;
        private boolean onlyWithReward;
        private boolean isUrgent;
    }
}