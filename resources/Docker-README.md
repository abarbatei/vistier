## Description
Solana Vistier API server. Useful for determining paid royalties by NFT owners.

## Overview
Image contains a flask server running the **Vistier API**. The API is mostly royalties oriented. 

More information here: https://github.com/abarbatei/vistier

## Settings
The server starts when the docker is started and runs on the **default 5000 port**.

It requires a Solana RPC endpoint to work. This image uses the public endpoint: https://api.mainnet-beta.solana.com

This endpoint is not that reliable, as such frequent **429 Too Many Requests** are returned. It is recommended that you use a private node operator/provider.

To change de default port, pass the environment variable **PORT** 

_Changing the endpoint is not supported_ on this image, please follow the instructions in the project github to build the image with the desired configuration.

There are several other configurations that can be set in order to drastically increase processing speed (but increase 429 Too Many Requests if the endpoint is not resilient enough).
For this image the following were used:
```
# how many transactions to process, backwards, looking for escrow TXs
ESCROW_TX_TO_PROCESS: 150

# the number of workers processing the above ESCROW_TX_TO_PROCESS, each being given an equal share
ESCROW_TX_PROCESSING_WORKERS: 1

# an extra safe, hard limit of how many TX to allow. It is a limiter to the above one
ESCROW_MAX_TX_TO_PROCESS: 1000

# how many transactions to process, backwards, looking for sales TXs per NFT (a wallet can hold many NFTs)
SALES_TX_TO_PROCESS_PER_NFT: 100

# the number of workers processing the above SALES_TX_TO_PROCESS_PER_NFT, each being given an equal share
SALES_TX_PROCESSING_WORKERS: 1

# an extra safe, hard limit of how many TX to allow. It is a limiter to the above SALES_TX_TO_PROCESS_PER_NFT
SALES_NFT_MAX_TX_TO_PROCESS: 1000

# how many NFTs belonging to the same collection to be, at max, processed. If there are more than this number
# of NFTs, although they will not be processed they are noted as belonging to the wallet
SALES_NFT_MAX_TO_INSPECT: 10

```

## Functionality

There are 2  implemented APIs:

- **/wallet-status** - checks the provided wallet address if it has the specific collection NFTs (indicated by the CMIDs, Candy Machine IDs). If found, will also show how much royalties did the wallet pay for the owned NFTs. Will also check for escrowed NFTs (i.e. that are not in the wallet at this time). Requires the following parameters:
    -  _address_: the wallet address to check for NFTs
    - _cmid_: Candy Machine ID for the targeted collection. They are usually the first creator address (if verified). Can look it up in Solana explorers or ask the collection creators. Parameter can appear multiple times, when there are multiple creators.

- **/marketplace-signature/\<signature-hash\>** - checks and identifies if the signature is a marketplace: Sell, Listing. Cancel Offer or Place Offer
