# Verifiable Shuffle Contracts

## verifiable_shuffle
### More Details
The commitment is stored in the Local Storage of the caller's account.
The reveal result will be linked back to the commitment such that the commitment is binding.
It's therefore in the interest of the committer to not clear state or opt out because they will lose their commitment.

The Commitment ID is hashed together with the seed to de-correlate similar commitments.  
For instance, if a two selection process are set for the same target block and the same parameters,
it would be possible to place bet on both outcomes and get selected at least once.  
The Commitment ID is actually the transaction ID of the `commit` method call.  
The `reveal` result contains the Commitment ID such that a result can be traced back to the right commitment.  
This makes each selection verifiable (the parameters were known before the outcome was known or predictable).

### Examples
Some use cases are demonstrated in the
[deployment script](./smart_contracts/verifiable_shuffle/deploy_config.py),
and in [testing](./tests/verifiable_shuffle_client_test.py).

### Safety Argument
The full version of this argument is available in the
[contract](./smart_contracts/verifiable_shuffle/contract.py) comments.

The number of possible selections for a given `(n,k)`-sized selection is `n! / (n - k)!`.  
Each initial seed from the Algorand Randomness Beacon is `256`-bit which can express `2^256` possible seeds.  
We want the ratio of these two quantities to be at least `2^128` to reduce the probability of two distinct seeds
creating the same list of winners to a negligible amount.  
In other words, we want the expected number of collisions to be negligible.

For this reason (and others, like numerical stability) we impose constraints on the input arguments:
- `n` is a `32`-bit number.
- `k` is a `8`-bit number.
- `k <= n`
- `log2(n! / (n - k)!) <= 128`

These conditions will be enforced by the contract. If you can't make a commitment, try reducing either `n` or `k`.

## mock_randomness_beacon
Used in LocalNet tests and deployments.
It implements the same interface as the real Algorand Randomness Beacon, but it returns a constant string.
This is used to keep the testing stable and predictable.

## verifiable_shuffle_opup
Auxiliary contract used to increase the opcode budget of `verifiable_shuffle` method execution.
This is slightly faster than using `ensure_budget` from Algorand Python because it re-uses the same app
instead of creating a new one each call.
Also, this prevents burning through app IDs on a public network.
