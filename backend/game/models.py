from django.db import models


class AppUser(models.Model):
    apple_sub = models.CharField(max_length=255, unique=True)   # Apple's stable user id
    email = models.EmailField(blank=True)
    display_name = models.CharField(max_length=40, blank=True)  # shown on leaderboards; blank = hidden
    created = models.DateTimeField(auto_now_add=True)


class Completion(models.Model):
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="completions")
    date = models.DateField()
    level = models.PositiveSmallIntegerField()          # 1 (easiest) .. 4 (hardest)
    seconds = models.PositiveIntegerField()
    hints = models.PositiveSmallIntegerField(default=0)
    checks = models.PositiveSmallIntegerField(default=0)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "date", "level"], name="one_result_per_puzzle")]
        indexes = [models.Index(fields=["date", "level", "seconds"])]   # leaderboard query
