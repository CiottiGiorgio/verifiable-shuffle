from typing import Final

SAFE_GAP: Final[str] = "The round delay is less than the safety parameters"
CREATOR: Final[str] = "Address is not the creator"
WINNERS_BOUND: Final[str] = "There must be at least one winner and less than 35"
PARTICIPANTS_BOUND: Final[str] = "There must be at least two participants"
INPUT_SOUNDNESS: Final[str] = "Winners must be less than or equal to Participants"
SAFE_SIZE: Final[str] = "The number of k-permutation exceeds the safety parameters"
ROUND_ELAPSED: Final[str] = "The committed round has not elapsed yet"
