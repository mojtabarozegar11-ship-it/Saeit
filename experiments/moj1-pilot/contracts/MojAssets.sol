// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;
import {TRC721} from "@openzeppelin/tron-contracts/token/TRC721/TRC721.sol";
import {TRC721URIStorage} from "@openzeppelin/tron-contracts/token/TRC721/extensions/TRC721URIStorage.sol";
import {Ownable} from "@openzeppelin/tron-contracts/access/Ownable.sol";

/// @notice Test collection. Only owner can create identifiable NFTs.
contract MojAssets is TRC721, TRC721URIStorage, Ownable {
    uint256 public constant MAX_ITEMS = 10_000;
    uint256 private _nextTokenId = 1;

    constructor(address collectionOwner)
        TRC721("Moj Digital Assets", "MOJA")
        Ownable(collectionOwner)
    { require(collectionOwner != address(0), "Invalid owner"); }

    function safeMint(address to, string calldata uri) external onlyOwner returns (uint256 tokenId) {
        require(_nextTokenId <= MAX_ITEMS, "Collection full");
        require(to != address(0), "Invalid recipient");
        require(bytes(uri).length != 0, "Missing metadata");
        tokenId = _nextTokenId++;
        _safeMint(to, tokenId);
        _setTokenURI(tokenId, uri);
    }

    function tokenURI(uint256 tokenId)
        public view override(TRC721, TRC721URIStorage) returns (string memory)
    { return super.tokenURI(tokenId); }

    function supportsInterface(bytes4 interfaceId)
        public view override(TRC721, TRC721URIStorage) returns (bool)
    { return super.supportsInterface(interfaceId); }
}
