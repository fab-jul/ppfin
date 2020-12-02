
# Goals

## Alpha 1

- [x] Account views
- [x] Update all
- [x] Find a name


## Alpha 2

- [x] Stocks
    - need a stocks table
    - has symbol, shares_change (how many shares bought/sold), price (price of the
    shares when bought/sold)
    - we can calc:
        - total number of shares (sum ofer shares_change), and from this:
          current value
        - total money spent on the shares
        - from the previous together: how much we made?
    - Show:
        SYM / NUM_SHARES / VALUE / GAIN
        
## Alpha 3

- [x] Unify GUI: show amounts in the right most column
- [x] Add date to transactions
    - [x] Show diff to prev entry in GUI
- [x] Unified formatting including currency handling
- [ ] Divide into liquid and non-liquid
    - [ ] Add a separate view for hold backs and non-liquids
- [ ] Document IBKR interaction, 
    - [ ] maybe automize
    
    
## Alpha 4

- [ ] Graphs?


## Future

- [ ] Vim bindings
