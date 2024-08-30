from typing import Literal, Tuple

from algopy import (
    ARC4Contract,
    BigUInt,
    Bytes,
    Global,
    LocalState,
    OnCompleteAction,
    OpUpFeeSource,
    TemplateVar,
    Txn,
    UInt64,
    arc4,
    ensure_budget,
    op,
    subroutine,
    urange,
)
from lib_pcg import pcg128_init, pcg128_random

# We desire to produce ordered k-permutations of the participants where n == participants, k == winners.
# The algorithm that we use to generate k-permutations wouldn't change if we wished to generate combinations.
# Therefore, the user could (wrongly) assume that it's equally safe to generate k-permutations or combination.
# This is not the case.
# The number of ordered k-permutations is n! / (n-k)!.
# The number of unordered combinations is (n choose k) == n! / ((n-k)!k!).
# In the worst case, the number of possible k-permutations is uncontrollably larger than the number of
#  possible combinations.
# The conceptual distinction between ordered k-permutations and unordered combinations is also difficult to grasp for
#  a general audience.

# For these reasons, we will make our safety arguments and advertise the features of this smart contract
#  in terms of k-permutations.
# Since we are using pseudo-randomness, we need to guarantee that our randomness seed size is appropriate for
#  the number of possible k-permutations.
# The seed not only needs to be strictly larger, but also overwhelmingly larger to prevent collisions in
#  the irregular mapping from seeds to k-permutations.
# https://en.wikipedia.org/wiki/Fisher%E2%80%93Yates_shuffle#Pseudorandom_generators

# Let's define some bounds on our inputs:
# The number of participants must be greater or equal to the number of winners (n >= k).
# A single seed produced with the Randomness Beacon is 256-bit.
# We want the ratio between the number of distinct pseudo-random sequences and
#  the number of k-permutations to be at least 2^128 (overwhelmingly larger).

# #distinct_prn_sequences / #k_permutations >= 2^128
# log2(#distinct_prn_sequences) - log2(#k_permutations) >= 128
# log2(#k_permutations) <= log2(2^256) - 128
# log2(#k_permutations) <= 128

# log2(n! / (n-k)!) = log2(n * (n-1) * ... * (n-k+1)) = log2(n) + log2(n-1) + ... + log2(n-k+1)
# In natural language, the sum of the logarithms of the numbers from n to n-k+1.
# This sum must be less than or equal to 128.

# For any #participants == n, the number of possible k-permutations is minimized by k == 1.
# Since:
# - log2(n! / (n-1)!) = log2(n)
# - log2(2^128 - 1) ~ 127,999
# - log2(2^128) = 128
# - log2(2^128 + 1) > 128
# When n >= 2^128 + 1, there does not exist an admissible k such that #k-permutations is safe to compute
#  with a 128-bit seed.
# Therefore, n fits in a 256-bit integer.

# However, this an enormous number of participants and would allow for a single winner at most.
# It would also force us to use BigUInt math everywhere and that's expensive.
# If participants was a 64-bit number, it would allow for 2 winners at most, but we could use native uint64 math.
# We are going to assume that participants is a 32-bit number because it allows 4 winners in the worst case
#  and native uint64 math.

# For any #winners == k, the number of possible k-permutations is minimized by n == k.
# Since:
# - log2(k! / (k-k)!) = log2(k!)
# - log2(34!) ~ 127,795
# - log2(35!) ~ 132,924
# When k >= 35, there does not exist an admissible n such that #k-permutations is safe to compute
#  with a 128-bit seed.
# Therefore, k fits in an 8-bit integer.


# The amount of fractional bits calculated for the logarithm.
LOGARITHM_FRACTIONAL_PRECISION = 10


class Commitment(arc4.Struct, kw_only=True):
    tx_id: arc4.StaticArray[arc4.Byte, Literal[32]]
    round: arc4.UInt64
    participants: arc4.UInt32
    winners: arc4.UInt8


class Reveal(arc4.Struct, kw_only=True):
    commitment_tx_id: arc4.StaticArray[arc4.Byte, Literal[32]]
    winners: arc4.DynamicArray[arc4.UInt32]


# https://mathsanew.com/articles/computing_logarithm_bit_by_bit.pdf
# https://en.wikipedia.org/wiki/Binary_logarithm#Iterative_approximation
@subroutine
def binary_logarithm(n: UInt64) -> UInt64:
    integer_component = op.bitlen(n) - UInt64(1)

    # We should now compute the fractional component of the logarithm with n / 2^integer_component as a float.
    # As we don't have access to floats, we will interpret from now on n as a fixed-point number with
    #  integer_component number of binary fractional digits.

    fractional_component = UInt64(0)

    # If n was a float at this point, this would be:
    # if n == 1:
    if n == (1 << integer_component):
        return fractional_component

    big_n = BigUInt(n)
    for _i in urange(LOGARITHM_FRACTIONAL_PRECISION):
        # n *= n
        big_n = (big_n * big_n) // BigUInt(1 << integer_component)
        # if n >= 2:
        if big_n >= (2 << integer_component):
            fractional_component = (fractional_component << 1) | UInt64(1)
            # n /= 2
            big_n = (big_n * BigUInt(1 << integer_component)) // BigUInt(
                2 << integer_component
            )
        else:
            fractional_component <<= UInt64(1)

    # We add the integer component to the fractional component AND we set the last bit to 1 because we want an
    #  upper bound on the logarithm.
    return (
        (integer_component << LOGARITHM_FRACTIONAL_PRECISION)
        | fractional_component
        | UInt64(1)
    )


class VerifiableGiveaway(ARC4Contract):
    def __init__(self) -> None:
        self.commitment = LocalState(Commitment)

    @arc4.baremethod(allow_actions=[OnCompleteAction.UpdateApplication])
    def update(self) -> None:
        assert Txn.sender == Global.creator_address

    @arc4.baremethod(allow_actions=[OnCompleteAction.DeleteApplication])
    def delete(self) -> None:
        assert Txn.sender == Global.creator_address

    # We need these getters because we are using template values.
    # If we store the template value in global state for easy reading,
    #  the state won't change automatically after a contract update.
    @arc4.abimethod(readonly=True)
    def get_templated_randomness_beacon_id(self) -> UInt64:
        return TemplateVar[UInt64]("RANDOMNESS_BEACON_ID")

    @arc4.abimethod(readonly=True)
    def get_templated_safety_round_gap(self) -> UInt64:
        return TemplateVar[UInt64]("SAFETY_ROUND_GAP")

    @arc4.abimethod(allow_actions=[OnCompleteAction.NoOp, OnCompleteAction.OptIn])
    def commit(
        self, delay: arc4.UInt8, participants: arc4.UInt32, winners: arc4.UInt8
    ) -> None:
        assert TemplateVar[UInt64]("SAFETY_ROUND_GAP") <= delay.native

        assert 1 <= winners.native
        assert 2 <= participants.native
        assert winners.native <= participants.native

        ensure_budget(700 * 2 * winners.native, OpUpFeeSource.GroupCredit)
        sum_of_logs = UInt64(0)
        for i in urange(
            participants.native - winners.native + 1, participants.native + 1
        ):
            sum_of_logs += binary_logarithm(i)
        assert sum_of_logs <= (128 << LOGARITHM_FRACTIONAL_PRECISION)

        self.commitment[Txn.sender] = Commitment(
            tx_id=arc4.StaticArray[arc4.Byte, Literal[32]].from_bytes(Txn.tx_id),
            round=arc4.UInt64(Global.round + delay.native),
            participants=participants,
            winners=winners,
        )

    @arc4.abimethod(allow_actions=[OnCompleteAction.NoOp, OnCompleteAction.CloseOut])
    def reveal(self) -> Reveal:
        commitment = self.commitment[Txn.sender].copy()
        del self.commitment[Txn.sender]

        committed_participants = commitment.participants.native
        committed_winners = commitment.winners.native

        assert Global.round >= commitment.round.native

        vrf_output, _txn = arc4.abi_call[arc4.DynamicBytes](
            "must_get",
            commitment.round,
            commitment.tx_id.bytes,
            app_id=TemplateVar[UInt64]("RANDOMNESS_BEACON_ID"),
        )

        state = pcg128_init(vrf_output.native)

        ensure_budget(700 * 50, OpUpFeeSource.GroupCredit)
        for i in urange(200):
            op.Scratch.store(i, Bytes())

        # Knuth shuffle.
        # We don't create a pre-initialized array of elements from 1 to participants because
        #  that could easily exceed the stack element size limit.
        # Instead, we assume that at position N lies the number N + 1.
        # Where that element has been changed, we will look it up in a dict-like data structure based on scratch space.
        # Scratch slot N will contain all key-value pairs where key % 200 == N.

        # We want to stop after "winners" iterations unless "winners" == "participants"
        #  in which case we want to stop at "participants" - 1.
        # We never need to shuffle the last element because it would just end up in the same position.
        n_shuffles = (
            committed_winners
            # We know that, by construction, "winners" <= "participants".
            if committed_winners < committed_participants
            else committed_participants - 1
        )
        # FIXME: We should check how much fee was provided for this call. If it's too much it's a draining attack
        #  and the contract should protect the user/funding account.
        ensure_budget(700 * n_shuffles, OpUpFeeSource.GroupCredit)
        for i in urange(n_shuffles):
            state, sequence = pcg128_random(
                state,
                BigUInt(i),
                BigUInt(committed_participants),
                UInt64(1),
            )
            j = op.extract_uint32(sequence[0].bytes, 12)

            i_bin = op.Scratch.load_bytes(i % UInt64(200))
            i_found, i_pos, i_value = linear_search(i_bin, i)

            j_bin = op.Scratch.load_bytes(j % UInt64(200))
            j_found, j_pos, j_value = linear_search(j_bin, j)

            if i_found:
                i_bin = op.replace(
                    i_bin, i_pos + 4, arc4.UInt32(j_value if j_found else j + 1).bytes
                )
            else:
                i_bin += (
                    arc4.UInt32(i).bytes
                    + arc4.UInt32(j_value if j_found else j + 1).bytes
                )

            if j_found:
                j_bin = op.replace(
                    j_bin, j_pos + 4, arc4.UInt32(i_value if i_found else i + 1).bytes
                )
            else:
                j_bin += (
                    arc4.UInt32(j).bytes
                    + arc4.UInt32(i_value if i_found else i + 1).bytes
                )
            op.Scratch.store(i % UInt64(200), i_bin)
            op.Scratch.store(j % UInt64(200), j_bin)

        winners = arc4.UInt16(committed_winners).bytes
        for i in urange(committed_winners):
            found, _pos, value = linear_search(
                op.Scratch.load_bytes(i % UInt64(200)), i
            )
            winners += arc4.UInt32(value).bytes if found else arc4.UInt32(i + 1).bytes

        return Reveal(
            commitment_tx_id=commitment.tx_id.copy(),
            winners=arc4.DynamicArray[arc4.UInt32].from_bytes(winners),
        )


@subroutine
def linear_search(bin_list: Bytes, key: UInt64) -> Tuple[bool, UInt64, UInt64]:
    for i in urange(UInt64(0), bin_list.length, UInt64(8)):
        bin_key = op.extract_uint32(bin_list, i)
        if bin_key == key:
            return True, i, op.extract_uint32(bin_list, i + 4)
    return False, UInt64(0), UInt64(0)
