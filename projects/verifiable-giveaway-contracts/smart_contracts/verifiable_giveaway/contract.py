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
    urange,
    subroutine,
)
from lib_pcg import pcg128_init, pcg128_random

# We desire to produce ordered k-permutations of the participants where k == winners.
# The number of k-permutations is n!/(n-k)!.
# In the worst case n == k and this collapses back to n!
# This is why we want to constrain the number of winners to be much less than the participants.
# The number of combinations in the worst case is significantly lower but the user
#  can always, incorrectly, assume that the results are ordered.
# This is why we derive these safety entropy parameters based on k-permutations.

# We want to guarantee that the ratio between the number of possible outcomes to this
#  winner selecting commitment is at least 2^128.
# https://en.wikipedia.org/wiki/Fisher%E2%80%93Yates_shuffle#Pseudorandom_generators
# #possible_prn_sequences / #possible_k_permutations >= 2^128
# log2(#possible_prn_sequences) - log2(#possible_k_permutations) >= 128
# log2(#possible_k_permutations) <= log2(2^256) - 128
# log2(#possible_k_permutations) <= 128

# First, some more arithmetic:
# log2(n! / (n-k)!) = log2(n * (n-1) * ... * (n-k+1)) = log2(n) + log2(n-1) + ... + log2(n-k+1)
# If this sum is less than 128, we can safely accept this commitment.


# The amount of fractional bits calculated for the logarithm.
LOGARITHM_FRACTIONAL_PRECISION = 10


class Commitment(arc4.Struct, kw_only=True):
    commitment_tx_id: arc4.StaticArray[arc4.Byte, Literal[32]]
    committed_block: arc4.UInt64
    committed_participants: arc4.UInt16
    committed_winners: arc4.UInt16


class RevealOutcome(arc4.Struct, kw_only=True):
    commitment_tx_id: arc4.StaticArray[arc4.Byte, Literal[32]]
    winners: arc4.DynamicArray[arc4.UInt16]


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
        self.active_commitment = LocalState(Commitment)

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
        self, delay: arc4.UInt8, participants: arc4.UInt16, winners: arc4.UInt16
    ) -> None:
        assert TemplateVar[UInt64]("SAFETY_ROUND_GAP") <= delay.native

        assert 1 <= winners.native
        assert 2 <= participants.native
        assert winners.native <= participants.native

        ensure_budget(700 * 2 *winners.native, OpUpFeeSource.GroupCredit)
        sum_of_logs = UInt64(0)
        for i in urange(participants.native - winners.native + 1, participants.native + 1):
            sum_of_logs += binary_logarithm(i)
        assert sum_of_logs <= (128 << LOGARITHM_FRACTIONAL_PRECISION)

        self.active_commitment[Txn.sender] = Commitment(
            commitment_tx_id=arc4.StaticArray[arc4.Byte, Literal[32]].from_bytes(
                Txn.tx_id
            ),
            committed_block=arc4.UInt64(Global.round + delay.native),
            committed_participants=participants,
            committed_winners=winners,
        )

    @arc4.abimethod(allow_actions=[OnCompleteAction.NoOp, OnCompleteAction.CloseOut])
    def reveal(self) -> RevealOutcome:
        active_commitment = self.active_commitment[Txn.sender].copy()
        del self.active_commitment[Txn.sender]

        committed_participants = active_commitment.committed_participants.native
        committed_winners = active_commitment.committed_winners.native

        assert Global.round >= active_commitment.committed_block.native

        vrf_output, _txn = arc4.abi_call[arc4.DynamicBytes](
            "must_get",
            active_commitment.committed_block,
            active_commitment.commitment_tx_id.bytes,
            app_id=TemplateVar[UInt64]("RANDOMNESS_BEACON_ID"),
        )

        state = pcg128_init(vrf_output.native)

        ensure_budget(700 * 50, OpUpFeeSource.GroupCredit)
        for i in urange(200):
            op.Scratch.store(i, Bytes())

        # Knuth shuffle.
        # We don't create a pre-initialized array of elements from 1 to participants because
        # that could easily exceed the stack element size limit.
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
                i_bin = op.replace(i_bin, i_pos+2, arc4.UInt16(j_value if j_found else j + 1).bytes)
            else:
                i_bin += arc4.UInt16(i).bytes + arc4.UInt16(j_value if j_found else j + 1).bytes

            if j_found:
                j_bin = op.replace(j_bin, j_pos+2, arc4.UInt16(i_value if i_found else i + 1).bytes)
            else:
                j_bin += arc4.UInt16(j).bytes + arc4.UInt16(i_value if i_found else i + 1).bytes
            op.Scratch.store(i % UInt64(200), i_bin)
            op.Scratch.store(j % UInt64(200), j_bin)

        winners = arc4.UInt16(committed_winners).bytes
        for i in urange(committed_winners):
            found, _pos, value = linear_search(op.Scratch.load_bytes(i % UInt64(200)), i)
            winners += arc4.UInt16(value).bytes if found else arc4.UInt16(i + 1).bytes

        return RevealOutcome(
            commitment_tx_id=active_commitment.commitment_tx_id.copy(),
            winners=arc4.DynamicArray[arc4.UInt16].from_bytes(winners),
        )


@subroutine
def linear_search(bin_list: Bytes, key: UInt64) -> Tuple[bool, UInt64, UInt64]:
    for i in urange(UInt64(0), bin_list.length, UInt64(4)):
        bin_key = op.extract_uint16(bin_list, i)
        if bin_key == key:
            return True, i, op.extract_uint16(bin_list, i + 2)
    return False, UInt64(0), UInt64(0)
