# Verifiable Shuffle

**Verifiable Shuffle** is an Algorand Smart Contract that can be used to select the winners of a
random selection process (lottery, giveaway, etc.).
The result is a list of `k` winners selected from `0, ..., n-1`, where `n` is number of participants.
Verifiable Shuffle implements safety mechanisms to make sure that each possible selection is equally likely.

It is based on the [Knuth's shuffle](https://en.wikipedia.org/wiki/Fisher%E2%80%93Yates_shuffle) algorithm and
the PRNG library [lib-pcg-avm](https://github.com/CiottiGiorgio/lib-pcg-avm).

The initial seed for the algorithm is gathered through the
[Algorand Randomness Beacon](https://developer.algorand.org/articles/randomness-on-algorand/).
This application also implements the commitment scheme outlined in the
[Best Practices](https://developer.algorand.org/articles/usage-and-best-practices-for-randomness-beacon/) for the Randomness Beacon.

## Disclaimer
This application is not audited for soundness and safety. It’s also still a work in progress.
Use at your own risk. See [MIT License](./LICENSE).

## Deployment
The app is currently available on TestNet on AppID `720180206`.
If you are not using automatic resource population, make sure to include the auxiliary AppID `720338984`
in the foreign app array.

## Features and Usage
This application implements two methods: `commit` & `reveal`.
Users of this application need to commit to the selection parameters `(participants, winners, block_delay)`
and, once the target block has been published, they will be able to reveal the selected winners.

Verifiable Shuffle can be used with an `ApplicationCall` or an `InnerApplicationCall` to either:
- Record the list of winners on the ledger.
- Be used by other applications that wish to use the list of winners for their business logic.

There are limits to the size of the selection process designed to keep each selection safe.
More details in the contract's [README](./projects/verifiable-shuffle).

## Why Should I Use This dApp?
Pseudo-randomness can be tricky to do right. In this project I made a priority that:
- The initial random seed is extracted correctly and cannot be predicted or forged.
- Selections with similar parameters are not correlated with each other.
- The commitment scheme is strong. It can't be later modified or re-tried.
- The implementation of Knuth's shuffle is sound and covers all edge cases.
- The size of the selection process is adequate for the amount of randomness that we currently extract from the Randomness Beacon.
- The algorithm is as fast as possible from an opcode economy perspective while still being safe.
- The underlying PRNG is of good quality.
