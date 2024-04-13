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
    itxn,
    op,
    urange,
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

# We are going to set more than one pair of safety parameters to allow the user to tradeoff participants for winners.
# log2(255!/(255-16)!) ~ 127,217
# log2(80!/(80-20)!)   ~ 122,694
# log2(47!/(47-25)!)   ~ 127,435
# log2(35!/(35-30)!)   ~ 126,018
# We conclude that any possible commitment involving at participants and winners at most these parameters is safe to
# compute given our entropy level (256 bits of vrf output).


class VerifiableGiveaway(ARC4Contract):
    def __init__(self) -> None:
        self.active_commitment = LocalState(Bytes)

    @arc4.baremethod(allow_actions=[OnCompleteAction.UpdateApplication])
    def update(self) -> None:
        assert Txn.sender == Global.creator_address

    @arc4.baremethod(allow_actions=[OnCompleteAction.DeleteApplication])
    def delete(self) -> None:
        assert Txn.sender == Global.creator_address

    @arc4.abimethod(allow_actions=[OnCompleteAction.NoOp, OnCompleteAction.OptIn])
    def commit(
        self, block: arc4.UInt64, participants: arc4.UInt8, winners: arc4.UInt8
    ) -> None:
        assert Global.round <= block.native - TemplateVar[UInt64]("SAFETY_ROUND_GAP")

        assert 1 <= winners.native
        assert 2 <= participants.native
        assert (
            # We don't need to actually check that participants is <= 255 because participants is arc4.UInt8
            (winners.native <= 16)
            or (participants.native <= 80 and winners.native <= 20)
            or (participants.native <= 47 and winners.native <= 25)
            or (participants.native <= 35 and winners.native <= 30)
        )
        assert winners.native <= participants.native

        # FIXME: It would be best to use a struct so that we have easier decoding off-chain.
        self.active_commitment[Txn.sender] = (
            Txn.tx_id + block.bytes + participants.bytes + winners.bytes
        )

    @arc4.abimethod(allow_actions=[OnCompleteAction.NoOp, OnCompleteAction.CloseOut])
    def reveal(self) -> tuple[arc4.DynamicBytes, arc4.DynamicArray[arc4.UInt8]]:
        committed_tx_id = arc4.DynamicBytes(self.active_commitment[Txn.sender][0:32])
        committed_block = arc4.UInt64.from_bytes(
            self.active_commitment[Txn.sender][32:40]
        )
        committed_participants = arc4.UInt8.from_bytes(
            self.active_commitment[Txn.sender][40:41]
        )
        committed_winners = arc4.UInt8.from_bytes(
            self.active_commitment[Txn.sender][41:42]
        )
        del self.active_commitment[Txn.sender]

        assert Global.round >= committed_block.native

        entropy_call = itxn.ApplicationCall(
            app_id=TemplateVar[UInt64]("RANDOMNESS_BEACON_ID"),
            app_args=(
                arc4.arc4_signature("must_get(uint64,byte[])byte[]"),
                committed_block.bytes,
                committed_tx_id.bytes,
            ),
            fee=0,
        ).submit()

        vrf_output = arc4.DynamicBytes.from_log(entropy_call.last_log)

        state1, state2, state3, state4 = pcg128_init(vrf_output.native)

        # Knuth shuffle.
        # We use a "truncated" version of the algorithm where we stop after "winners" iterations.
        # The array to be shuffled is an array with the numbers from 1 to "participants".
        # Since we have constrained "participants", we can populate the array in constant time
        #  by slicing a pre-computed bytearray with numbers from 1 to 255 (arc4.UInt8 max value).
        participants = Bytes.from_hex(
            "0102030405060708090a0b0c0d0e0f10"
            "1112131415161718191a1b1c1d1e1f20"
            "2122232425262728292a2b2c2d2e2f30"
            "3132333435363738393a3b3c3d3e3f40"
            "4142434445464748494a4b4c4d4e4f50"
            "5152535455565758595a5b5c5d5e5f60"
            "6162636465666768696a6b6c6d6e6f70"
            "7172737475767778797a7b7c7d7e7f80"
            "8182838485868788898a8b8c8d8e8f90"
            "9192939495969798999a9b9c9d9e9fa0"
            "a1a2a3a4a5a6a7a8a9aaabacadaeafb0"
            "b1b2b3b4b5b6b7b8b9babbbcbdbebfc0"
            "c1c2c3c4c5c6c7c8c9cacbcccdcecfd0"
            "d1d2d3d4d5d6d7d8d9dadbdcdddedfe0"
            "e1e2e3e4e5e6e7e8e9eaebecedeeeff0"
            "f1f2f3f4f5f6f7f8f9fafbfcfdfeff"
        )[: committed_participants.native]
        # We want to stop after "winners" iterations unless "winners" == "participants"
        #  in which case we want to stop at "participants" - 1.
        # We never need to shuffle the last element because it would just end up in the same position.
        n_shuffles = (
            committed_winners.native
            # We know that, by construction, "winners" <= "participants".
            if committed_winners.native < committed_participants.native
            else committed_participants.native - 1
        )
        # FIXME: We should check how much fee was provided for this call. If it's too much it's a draining attack
        #  and the contract should protect the user/funding account.
        ensure_budget(700 * n_shuffles, OpUpFeeSource.GroupCredit)
        for i in urange(n_shuffles):
            state1, state2, state3, state4, r_bytes = pcg128_random(
                (state1, state2, state3, state4),
                BigUInt(i),
                BigUInt(committed_participants.native),
                UInt64(1),
            )
            r = op.getbyte(r_bytes, 17)
            participants_i = op.getbyte(participants, i)
            participants_r = op.getbyte(participants, r)
            participants = op.setbyte(participants, i, participants_r)
            participants = op.setbyte(participants, r, participants_i)

        return committed_tx_id.copy(), arc4.DynamicArray[arc4.UInt8].from_bytes(
            arc4.UInt16(committed_winners.native).bytes
            + participants[: committed_winners.native]
        )
