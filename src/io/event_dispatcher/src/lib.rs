//! NATS connection and handshake checks.
//! This bootstrap probe is not a production publisher or JetStream client SDK.
use std::io::{self, BufRead, BufReader, Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::time::Duration;

pub struct JetStreamConnection {
    reader: BufReader<TcpStream>,
}

impl JetStreamConnection {
    /// Connect to a live server and complete the NATS INFO/CONNECT/PING exchange.
    pub fn connect(address: SocketAddr, timeout: Duration) -> io::Result<Self> {
        let stream = TcpStream::connect_timeout(&address, timeout)?;
        stream.set_read_timeout(Some(timeout))?;
        stream.set_write_timeout(Some(timeout))?;
        let mut connection = Self {
            reader: BufReader::new(stream),
        };
        if !connection.read_line()?.starts_with("INFO {") {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "expected NATS INFO",
            ));
        }
        connection.reader.get_mut().write_all(
            b"CONNECT {\"verbose\":false,\"pedantic\":true,\"lang\":\"rust\",\"version\":\"0.1.0\"}\r\n",
        )?;
        connection.ping()?;
        Ok(connection)
    }

    fn read_line(&mut self) -> io::Result<String> {
        let mut bytes = Vec::new();
        self.reader
            .by_ref()
            .take(65537)
            .read_until(b'\n', &mut bytes)?;
        if bytes.len() > 65536 || !bytes.ends_with(b"\r\n") {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid NATS line",
            ));
        }
        String::from_utf8(bytes).map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))
    }

    /// Check a real broker round trip; fail on protocol errors or bounded timeout.
    pub fn ping(&mut self) -> io::Result<()> {
        self.reader.get_mut().write_all(b"PING\r\n")?;
        for _ in 0..32 {
            let line = self.read_line()?;
            match line.trim_end() {
                "PONG" => return Ok(()),
                "PING" => self.reader.get_mut().write_all(b"PONG\r\n")?,
                "+OK" => (),
                other if other.starts_with("INFO ") => (),
                _ => return Err(io::Error::new(io::ErrorKind::InvalidData, line)),
            }
        }
        Err(io::Error::new(
            io::ErrorKind::TimedOut,
            "no PONG after 32 frames",
        ))
    }
}
