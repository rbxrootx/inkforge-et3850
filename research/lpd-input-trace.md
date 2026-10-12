# LPR port 515 input trace

The live printer listens on TCP 515. The extracted `nwsoc` program's receive routine `0x16920` reads LPR job data and control records from the socket. This is an offline first-pass trace, not a vulnerability finding.

- The control-record parser copies `H`, `J`, `N`, and `P` values into separate global fields after checks limiting them to 127 or 255 bytes. The job data goes into an allocated buffer and then into the program's internal print submission calls.
- The client-supplied data-file name enters `0xdde64` through metadata helpers `0xe051c` and `0xe06c0`. `0xdde64` parses a `dfA`-style name into a fixed-length submission identifier. These immediate functions do not call `open`, `fopen`, or a shell with that filename.
- The receive routine caps the accepted data chunk size by its allocated buffer. Its LPR command-line parser has a fixed stack boundary check before writing another byte.

The visible filename path does not supply the arbitrary Linux file write needed to place `/opt/nwsoc_data/ExtBoot`. Deeper print pipeline components and other LPR input effects remain outside this narrow trace. No LPR job or malformed command was sent to the printer during this analysis.
