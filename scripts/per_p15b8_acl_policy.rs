// P15-B8: Linux-only, owner-applied STRICT POSIX ACL for the optional
// OEM mediad local detections endpoint. Included in an ephemeral OEM tree.
// No subprocess, libacl dependency, service, credential elevation, or motor IO.
// The OS owner of the directory/socket applies both ACLs synchronously BEFORE
// a listener is returned. Fail closed on missing user/xattr or unexpected ACL.
use std::ffi::CString;
use std::os::unix::ffi::OsStrExt;
use std::os::unix::fs::{FileTypeExt, MetadataExt, PermissionsExt};
use std::path::Path;

use anyhow::{Context, Result, bail};

const ACL_NAME: &[u8] = b"system.posix_acl_access\0";
const ACL_VERSION: u32 = 0x0002;
const UNDEF_ID: u32 = u32::MAX;
const ACL_USER_OBJ: u16 = 0x01;
const ACL_USER: u16 = 0x02;
const ACL_GROUP_OBJ: u16 = 0x04;
const ACL_MASK: u16 = 0x10;
const ACL_OTHER: u16 = 0x20;

#[derive(Clone, Copy, PartialEq, Eq)]
enum Access {
    Directory,
    Socket,
}

fn check_observer(uid: u32) -> Result<()> {
    if uid == 0 || uid == unsafe { libc::geteuid() } {
        bail!("observer UID must be separate from root and the mediad owner");
    }
    Ok(())
}

fn c_path(path: &Path) -> Result<CString> {
    CString::new(path.as_os_str().as_bytes()).context("invalid NUL in metadata path")
}

fn expected_acl(uid: u32, access: Access) -> Vec<u8> {
    let owner = if access == Access::Directory { 0o7 } else { 0o6 };
    let named = if access == Access::Directory { 0o1 } else { 0o6 };
    let mut bytes = ACL_VERSION.to_ne_bytes().to_vec();
    for (tag, perm, id) in [
        (ACL_USER_OBJ, owner, UNDEF_ID),
        (ACL_USER, named, uid),
        (ACL_GROUP_OBJ, 0, UNDEF_ID),
        (ACL_MASK, named, UNDEF_ID),
        (ACL_OTHER, 0, UNDEF_ID),
    ] {
        bytes.extend_from_slice(&tag.to_ne_bytes());
        bytes.extend_from_slice(&perm.to_ne_bytes());
        bytes.extend_from_slice(&id.to_ne_bytes());
    }
    bytes
}

fn read_acl(path: &Path) -> Result<Option<Vec<u8>>> {
    let path = c_path(path)?;
    // Strict bounded read: the approved 5-entry ACL occupies 44 bytes.
    // No dynamic allocation or silent acceptance of extra POSIX ACL entries.
    let mut data = [0_u8; 128];
    let size = unsafe {
        libc::lgetxattr(
            path.as_ptr(),
            ACL_NAME.as_ptr().cast(),
            data.as_mut_ptr().cast(),
            data.len(),
        )
    };
    if size < 0 {
        let error = std::io::Error::last_os_error();
        if error.raw_os_error() == Some(libc::ENODATA) {
            return Ok(None);
        }
        return Err(error).context("read access ACL failed (unsupported is STOP)");
    }
    Ok(Some(data[..size as usize].to_vec()))
}

fn install_acl(path: &Path, acl: &[u8]) -> Result<()> {
    let path = c_path(path)?;
    // CREATE refuses overwriting a pre-existing ACL from another principal.
    let rc = unsafe {
        libc::lsetxattr(
            path.as_ptr(),
            ACL_NAME.as_ptr().cast(),
            acl.as_ptr().cast(),
            acl.len(),
            libc::XATTR_CREATE,
        )
    };
    if rc != 0 {
        return Err(std::io::Error::last_os_error()).context("create strict access ACL failed");
    }
    Ok(())
}

fn metadata(path: &Path) -> Result<std::fs::Metadata> {
    std::fs::symlink_metadata(path).context("metadata inode missing")
}

fn strict_private_dir(path: &Path, uid: u32) -> Result<()> {
    check_observer(uid)?;
    let info = metadata(path)?;
    if !info.file_type().is_dir() || info.uid() != unsafe { libc::geteuid() } {
        bail!("private metadata directory has unexpected type/owner");
    }
    let mode = info.permissions().mode() & 0o777;
    match read_acl(path)? {
        None if mode == 0o700 => Ok(()),
        Some(actual)
            if mode == 0o710 && actual == expected_acl(uid, Access::Directory) =>
        {
            Ok(())
        }
        _ => bail!("private metadata directory ACL/mode is not strictly approved"),
    }
}

/// Close traversal BEFORE binding a new inode. A Unix pathname socket starts
/// with the process umask's permissions; while the listener is not returned,
/// a different thread/process might still reach it before chmod(0600).
/// Revoke ONLY our known exact named ACL and make the directory owner-only.
/// The directory access grant is deliberately the LAST step before returning
/// the listener. Never change a foreign/unknown ACL.
pub(super) fn hide_private_dir_before_bind(path: &Path, uid: u32) -> Result<()> {
    strict_private_dir(path, uid)?;
    if read_acl(path)?.is_some() {
        let name = c_path(path)?;
        let rc = unsafe { libc::lremovexattr(name.as_ptr(), ACL_NAME.as_ptr().cast()) };
        if rc != 0 {
            return Err(std::io::Error::last_os_error())
                .context("could not revoke directory traversal before socket rebind");
        }
    }
    if read_acl(path)?.is_some()
        || metadata(path)?.permissions().mode() & 0o777 != 0o700
    {
        bail!("private directory was not closed before binding a new socket");
    }
    Ok(())
}

pub(super) fn grant_private_dir(path: &Path, uid: u32) -> Result<()> {
    strict_private_dir(path, uid)?;
    if read_acl(path)?.is_none() {
        install_acl(path, &expected_acl(uid, Access::Directory))?;
    }
    // Revalidate the exact UID, mask and group entries after the kernel writes
    // the xattr. Mode 0710 is NOT access for group::--- or other::---.
    if read_acl(path)?.as_deref() != Some(expected_acl(uid, Access::Directory).as_slice())
        || metadata(path)?.permissions().mode() & 0o777 != 0o710
    {
        bail!("private metadata directory ACL failed read-back verification");
    }
    Ok(())
}

pub(super) fn check_dir(path: &Path, uid: u32) -> Result<()> {
    strict_private_dir(path, uid)
}

pub(super) fn grant_socket(path: &Path, uid: u32) -> Result<()> {
    check_observer(uid)?;
    let info = metadata(path)?;
    if !info.file_type().is_socket()
        || info.uid() != unsafe { libc::geteuid() }
        || info.permissions().mode() & 0o777 != 0o600
        || read_acl(path)?.is_some()
    {
        bail!("socket not a fresh owner-only inode; refusing ACL grant");
    }
    let acl = expected_acl(uid, Access::Socket);
    install_acl(path, &acl)?;
    if read_acl(path)?.as_deref() != Some(acl.as_slice())
        || metadata(path)?.permissions().mode() & 0o777 != 0o660
    {
        bail!("metadata socket ACL failed strict read-back verification");
    }
    Ok(())
}

/// Look up the *named* dedicated observer identity in the installed OS.
/// No arbitrary numeric UID, environment variable or group fallback is used
/// by bind_default(). A missing user is a STOP, not a new account creation.
pub(super) fn observer_uid() -> Result<u32> {
    let mut entry: libc::passwd = unsafe { std::mem::zeroed() };
    let mut matched: *mut libc::passwd = std::ptr::null_mut();
    let mut buf = [0_i8; 4096];
    let rc = unsafe {
        libc::getpwnam_r(
            c"kwipi".as_ptr(),
            &mut entry,
            buf.as_mut_ptr(),
            buf.len(),
            &mut matched,
        )
    };
    if rc != 0 || matched.is_null() {
        bail!("dedicated kwipi account missing or NSS lookup failed");
    }
    check_observer(entry.pw_uid)?;
    Ok(entry.pw_uid)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::{DirBuilderExt, PermissionsExt};

    const FIXTURE_KWIPI_UID: u32 = 31053;

    fn fake_private() -> (tempfile::TempDir, std::path::PathBuf) {
        let tmp = tempfile::tempdir().unwrap();
        let dir = tmp.path().join("kwipi");
        std::fs::DirBuilder::new().mode(0o700).create(&dir).unwrap();
        (tmp, dir)
    }

    #[test]
    fn strict_dir_accepts_exact_acl_and_rejects_other_uid() {
        let (_tmp, dir) = fake_private();
        assert!(check_dir(&dir, FIXTURE_KWIPI_UID).is_ok());
        grant_private_dir(&dir, FIXTURE_KWIPI_UID).unwrap();
        assert_eq!(metadata(&dir).unwrap().permissions().mode() & 0o777, 0o710);
        assert!(check_dir(&dir, FIXTURE_KWIPI_UID).is_ok());
        assert!(check_dir(&dir, FIXTURE_KWIPI_UID + 1).is_err());
        assert!(grant_private_dir(&dir, FIXTURE_KWIPI_UID).is_ok());
        assert!(grant_private_dir(&dir, FIXTURE_KWIPI_UID + 1).is_err());
    }

    #[test]
    fn rejects_other_user_group_or_mask_permissions_without_chmod() {
        let (_tmp, dir) = fake_private();
        let mut acl = expected_acl(FIXTURE_KWIPI_UID, Access::Directory);
        // group::r-- rather than group::--- is a forbidden broadened ACL.
        acl[4 + 2 * 8 + 2] = 4;
        install_acl(&dir, &acl).unwrap();
        assert!(check_dir(&dir, FIXTURE_KWIPI_UID).is_err());
        assert!(grant_private_dir(&dir, FIXTURE_KWIPI_UID).is_err());
        assert!(check_dir(&dir, FIXTURE_KWIPI_UID + 1).is_err());
    }

    #[test]
    fn revokes_previous_directory_acl_before_new_socket_bind() {
        let (_tmp, dir) = fake_private();
        grant_private_dir(&dir, FIXTURE_KWIPI_UID).unwrap();
        assert_eq!(metadata(&dir).unwrap().permissions().mode() & 0o777, 0o710);
        hide_private_dir_before_bind(&dir, FIXTURE_KWIPI_UID).unwrap();
        assert_eq!(metadata(&dir).unwrap().permissions().mode() & 0o777, 0o700);
        assert!(read_acl(&dir).unwrap().is_none());
        // Regranting traversal belongs at the END of the bind sequence.
        grant_private_dir(&dir, FIXTURE_KWIPI_UID).unwrap();
        assert!(hide_private_dir_before_bind(&dir, FIXTURE_KWIPI_UID + 1).is_err());
        assert_eq!(metadata(&dir).unwrap().permissions().mode() & 0o777, 0o710);
    }

    #[test]
    fn refuses_symlink_or_root_or_owner_uid() {
        let (tmp, dir) = fake_private();
        assert!(check_dir(&dir, 0).is_err());
        assert!(check_dir(&dir, unsafe { libc::geteuid() }).is_err());
        let link = tmp.path().join("linked");
        std::os::unix::fs::symlink(&dir, &link).unwrap();
        assert!(check_dir(&link, FIXTURE_KWIPI_UID).is_err());
    }

    #[tokio::test]
    async fn grants_acl_to_fresh_socket_only_and_rechecks_after_rebind() {
        let (_tmp, dir) = fake_private();
        let path = dir.join("detections.sock");
        // Actual kernel-backed Unix inode, no camera or RPC.
        let first = super::super::bind_with_uid(&path, FIXTURE_KWIPI_UID).unwrap();
        assert_eq!(metadata(&path).unwrap().permissions().mode() & 0o777, 0o660);
        assert_eq!(
            read_acl(&path).unwrap().unwrap(),
            expected_acl(FIXTURE_KWIPI_UID, Access::Socket),
        );
        assert!(super::super::bind_with_uid(&path, FIXTURE_KWIPI_UID).is_err());
        drop(first);
        std::fs::remove_file(&path).unwrap();
        // Prior inode ACL is gone, but directory ACL remains strictly checked.
        let next = super::super::bind_with_uid(&path, FIXTURE_KWIPI_UID).unwrap();
        assert_eq!(
            read_acl(&path).unwrap().unwrap(),
            expected_acl(FIXTURE_KWIPI_UID, Access::Socket),
        );
        assert!(super::super::bind_with_uid(&path, FIXTURE_KWIPI_UID + 1).is_err());
        drop(next);
    }

    #[test]
    fn rejects_a_socket_path_preexisting_as_file() {
        let (_tmp, dir) = fake_private();
        let path = dir.join("detections.sock");
        std::fs::write(&path, "not a socket").unwrap();
        assert!(super::super::bind_with_uid(&path, FIXTURE_KWIPI_UID).is_err());
    }
}
