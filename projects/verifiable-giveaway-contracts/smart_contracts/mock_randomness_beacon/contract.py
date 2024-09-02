# pyright: reportMissingModuleSource=false
from algopy import ARC4Contract, Bytes, TemplateVar, arc4


class MockRandomnessBeacon(ARC4Contract):
    @arc4.abimethod
    def must_get(
        self, round: arc4.UInt64, user_data: arc4.DynamicBytes  # noqa: A002
    ) -> arc4.DynamicBytes:
        return arc4.DynamicBytes(TemplateVar[Bytes]("VRF_OUTPUT"))
