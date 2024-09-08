from algopy import ARC4Contract, arc4


class VerifiableShuffleOpup(ARC4Contract):
    @arc4.baremethod(create="allow")
    def opup(self) -> None:
        pass
